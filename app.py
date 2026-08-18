import hmac
import hashlib
import uuid
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ============================================================================
# LOOP MERCHANT CONFIGURATION
# Get these from your LOOP Business Dashboard (https://business.loop.co.ke)
# ============================================================================
LOOP_CONFIG = {
    "SECRET_KEY": "your_secret_key_here",      # From LOOP Dashboard
    "MERCHANT_TILL": "472042",                  # Your LOOP till number
    # LOOP Sandbox M-Pesa Prompt Gateway
    "PROMPT_URL": "https://sandbox.loop.co.ke/gateway/mpesa-prompt/2.0/services/process-request",
    # Production URL (uncomment when ready)
    # "PROMPT_URL": "https://api.loop.co.ke/gateway/mpesa-prompt/2.0/services/process-request",
}

# In-memory transaction store (replace with database in production)
transactions = {}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_reference():
    """Generate a unique transaction reference"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_id = str(uuid.uuid4())[:8].upper()
    return f"STC-{timestamp}-{random_id}"


def generate_timestamp():
    """Generate UTC timestamp in ISO 8601 format"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_nonce():
    """Generate a unique nonce"""
    return str(uuid.uuid4())


def compute_hmac_signature(data_dict, secret_key):
    """
    Compute HMAC-SHA256 signature for LOOP request.
    Sort keys and create canonical JSON string.
    """
    try:
        # Create canonical JSON (sorted keys, no spaces)
        canonical = json.dumps(data_dict, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            secret_key.encode(),
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    except Exception as e:
        logger.error(f"Signature computation error: {e}")
        raise


def normalize_phone(phone):
    """Convert phone to 254XXXXXXXXX format"""
    phone = str(phone).strip()
    # Remove + if present
    if phone.startswith("+"):
        phone = phone[1:]
    # Convert 07/01 to 254
    if phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]
    # Ensure it starts with 254
    if not phone.startswith("254"):
        phone = "254" + phone
    return phone


def validate_request_signature(data, signature, secret_key):
    """Validate incoming webhook signature"""
    try:
        computed_sig = compute_hmac_signature(data, secret_key)
        return hmac.compare_digest(computed_sig, signature)
    except Exception as e:
        logger.error(f"Signature validation error: {e}")
        return False


# ============================================================================
# LOOP STK PUSH - Initiate M-Pesa Prompt
# ============================================================================

@app.route('/api/loop/initiate-payment', methods=['POST'])
def initiate_payment():
    """
    Initiate LOOP M-Pesa STK Push payment prompt.
    
    Request body:
    {
        "phone": "254105087393" or "0105087393",
        "amount": 1000,
        "reference": "STC-260818-4821" (optional - generated if not provided),
        "till": "472042",
        "description": "Payment for Siniora Tech Cyber Service"
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({'error': 'No request body provided'}), 400
        
        phone = data.get('phone', '').strip()
        amount = data.get('amount')
        till = data.get('till', LOOP_CONFIG['MERCHANT_TILL'])
        description = data.get('description', 'Siniora Tech Cyber Payment')
        reference = data.get('reference') or generate_reference()
        
        # Normalize phone
        try:
            phone = normalize_phone(phone)
        except Exception as e:
            return jsonify({'error': f'Invalid phone number: {str(e)}'}), 400
        
        # Validate inputs
        if not phone:
            return jsonify({'error': 'Phone number is required'}), 400
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400
        
        try:
            amount = float(amount)
        except ValueError:
            return jsonify({'error': 'Amount must be a number'}), 400
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be greater than 0'}), 400
        if len(phone) != 12 or not phone.isdigit():
            return jsonify({'error': f'Invalid phone format. Expected 254XXXXXXXXX, got {phone}'}), 400
        
        logger.info(f"Initiating LOOP payment: {reference}, {amount} KSh to {phone}")
        
        # Prepare LOOP API payload
        payload = {
            "till": till,
            "phone_number": phone,
            "amount": int(amount),  # LOOP expects integer amount in cents or KSh
            "reference": reference,
            "description": description[:50],  # Limit description length
            "timestamp": generate_timestamp(),
            "nonce": generate_nonce()
        }
        
        # Compute signature on the payload
        signature = compute_hmac_signature(payload, LOOP_CONFIG['SECRET_KEY'])
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {signature}"
        }
        
        logger.info(f"Calling LOOP API: {LOOP_CONFIG['PROMPT_URL']}")
        logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Call LOOP API
        response = requests.post(
            LOOP_CONFIG['PROMPT_URL'],
            json=payload,
            headers=headers,
            timeout=10
        )
        
        response_data = response.json() if response.text else {}
        
        logger.info(f"LOOP Response Status: {response.status_code}")
        logger.debug(f"LOOP Response: {json.dumps(response_data, indent=2)}")
        
        # Store transaction record
        transactions[reference] = {
            "phone": phone,
            "amount": amount,
            "till": till,
            "description": description,
            "reference": reference,
            "status": "initiated",
            "initiated_at": datetime.now(timezone.utc).isoformat(),
            "loop_response": response_data,
            "loop_status_code": response.status_code
        }
        
        if response.status_code in [200, 201]:
            return jsonify({
                'success': True,
                'message': 'M-Pesa prompt sent successfully',
                'reference': reference,
                'phone': phone,
                'amount': amount,
                'data': response_data
            }), 200
        else:
            logger.warning(f"LOOP API error: {response_data}")
            error_msg = response_data.get('message') or response_data.get('error', 'Unknown error')
            return jsonify({
                'success': False,
                'message': 'Failed to initiate payment',
                'error': error_msg,
                'reference': reference
            }), response.status_code
    
    except requests.exceptions.Timeout:
        logger.error("LOOP API timeout")
        return jsonify({'error': 'Payment gateway timeout - please try again'}), 504
    except requests.exceptions.ConnectionError:
        logger.error("LOOP API connection error")
        return jsonify({'error': 'Cannot reach payment gateway'}), 502
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return jsonify({'error': 'Payment gateway error'}), 502
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# LOOP CALLBACK WEBHOOK - Receive Payment Confirmation
# ============================================================================

@app.route('/api/loop/callback', methods=['POST'])
def loop_callback():
    """
    LOOP sends payment confirmation here.
    
    Expected payload (with signature header):
    {
        "reference": "STC-260818-4821",
        "status": "completed" | "failed" | "pending",
        "amount": 1000,
        "phone": "254105087393",
        "transaction_id": "LOP1234567890"
    }
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not auth_header:
            logger.warning("Webhook received without Authorization header")
            return jsonify({'error': 'Missing authorization'}), 401
        
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'No payload'}), 400
        
        # Validate signature
        if not validate_request_signature(payload, auth_header, LOOP_CONFIG['SECRET_KEY']):
            logger.warning(f"Invalid webhook signature for reference: {payload.get('reference')}")
            return jsonify({'error': 'Invalid signature'}), 401
        
        reference = payload.get('reference')
        status = payload.get('status')
        
        logger.info(f"✓ Payment callback received: {reference}, status: {status}")
        
        # Update transaction status
        if reference in transactions:
            transactions[reference]['status'] = status
            transactions[reference]['callback_data'] = payload
            transactions[reference]['callback_received_at'] = datetime.now(timezone.utc).isoformat()
            
            if status == 'completed':
                logger.info(f"✓ Payment COMPLETED: {reference}")
                # TODO: Update order status in database
                # TODO: Send customer confirmation SMS/Email
            elif status == 'failed':
                logger.warning(f"✗ Payment FAILED: {reference}")
                # TODO: Update order status
                # TODO: Allow retry
            elif status == 'pending':
                logger.info(f"⏳ Payment PENDING: {reference}")
        else:
            logger.warning(f"Received callback for unknown reference: {reference}")
        
        # Always return 200 to acknowledge receipt
        return jsonify({'success': True, 'message': 'Callback acknowledged'}), 200
    
    except Exception as e:
        logger.error(f"Callback processing error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# PAYMENT STATUS CHECK
# ============================================================================

@app.route('/api/loop/status/<reference>', methods=['GET'])
def check_payment_status(reference):
    """Check the status of a payment by reference number"""
    if reference not in transactions:
        return jsonify({
            'error': 'Reference not found',
            'reference': reference
        }), 404
    
    trans = transactions[reference]
    return jsonify({
        'reference': reference,
        'status': trans['status'],
        'amount': trans['amount'],
        'phone': trans['phone'],
        'initiated_at': trans['initiated_at'],
        'callback_received': 'callback_received_at' in trans
    }), 200


# ============================================================================
# ADMIN - VIEW ALL TRANSACTIONS (for testing only - ADD AUTH IN PRODUCTION)
# ============================================================================

@app.route('/api/admin/transactions', methods=['GET'])
def view_transactions():
    """View all transactions (development only - add authentication in production)"""
    # TODO: Add authentication check
    return jsonify({
        'total': len(transactions),
        'transactions': {k: {
            'reference': v['reference'],
            'amount': v['amount'],
            'phone': v['phone'][-4:],  # Mask phone number
            'status': v['status'],
            'initiated_at': v['initiated_at']
        } for k, v in transactions.items()}
    }), 200


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'merchant_till': LOOP_CONFIG['MERCHANT_TILL'],
        'prompt_url': LOOP_CONFIG['PROMPT_URL'],
        'mode': 'sandbox' if 'sandbox' in LOOP_CONFIG['PROMPT_URL'] else 'production',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == '__main__':
    mode = 'SANDBOX' if 'sandbox' in LOOP_CONFIG['PROMPT_URL'] else 'PRODUCTION'
    print(f"""
    ╔════════════════════════════════════════════════════╗
    ║   SINIORA TECH CYBER - LOOP Payment Backend       ║
    ║         M-Pesa Payment Gateway (v2.0)             ║
    ╚════════════════════════════════════════════════════╝
    
    Configuration:
    - Merchant Till: {LOOP_CONFIG['MERCHANT_TILL']}
    - Mode: {mode}
    - Gateway: {LOOP_CONFIG['PROMPT_URL']}
    
    API Endpoints:
    ───────────────────────────────────────────────────
    Payment Endpoints:
    - POST   /api/loop/initiate-payment    Initiate STK Push
    - GET    /api/loop/status/<reference>  Check payment status
    
    Webhook:
    - POST   /api/loop/callback            Receive payment confirmation
    
    Admin (Development Only):
    - GET    /api/health                   Health check
    - GET    /api/admin/transactions       View all transactions
    
    Server: http://localhost:5000
    ───────────────────────────────────────────────────
    
    Next Steps:
    1. Update LOOP_CONFIG with your SECRET_KEY from LOOP Dashboard
    2. Run: pip install flask requests
    3. Run: python app.py
    4. Test: curl http://localhost:5000/api/health
    5. Configure LOOP callback URL: https://yourdomain.com/api/loop/callback
    """)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
