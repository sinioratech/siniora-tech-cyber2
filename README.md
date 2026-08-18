# LOOP M-Pesa Payment Integration Setup Guide

## 📋 Overview

This is a complete **M-Pesa payment integration** for Siniora Tech Cyber using the **LOOP Payment Gateway** (v2.0 Sandbox).

### Components:
- **Frontend**: `index.html` - Customer-facing payment portal with retry logic
- **Backend**: `app.py` - Flask server handling LOOP API calls
- **Dependencies**: `requirements.txt` - Python packages

---

## 🚀 Quick Start

### 1. **Install Dependencies**

```bash
# Create virtual environment (recommended)
python3 -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. **Get LOOP Credentials**

1. Go to **LOOP Business Dashboard**: https://business.loop.co.ke
2. Sign up for a **Business Account** (if you haven't already)
3. Navigate to **Settings → API Credentials** or **Developer Settings**
4. Copy your **SECRET_KEY** (also called API Secret or Private Key)
5. Verify your **Merchant Till**: `472042` ✓

### 3. **Configure Backend**

Edit `app.py` and update the `LOOP_CONFIG` section:

```python
LOOP_CONFIG = {
    "SECRET_KEY": "paste_your_secret_key_here",  # 🔑 FROM LOOP DASHBOARD
    "MERCHANT_TILL": "472042",                    # ✓ Your till number
    "PROMPT_URL": "https://sandbox.loop.co.ke/gateway/mpesa-prompt/2.0/services/process-request",
}
```

### 4. **Run the Backend Server**

```bash
python app.py
```

You should see:
```
╔════════════════════════════════════════════════════╗
║   SINIORA TECH CYBER - LOOP Payment Backend       ║
║         M-Pesa Payment Gateway (v2.0)             ║
╚════════════════════════════════════════════════════╝

Configuration:
- Merchant Till: 472042
- Mode: SANDBOX
- Gateway: https://sandbox.loop.co.ke/...

Server: http://localhost:5000
```

### 5. **Test the API**

```bash
# Health check
curl http://localhost:5000/api/health

# Test payment initiation
curl -X POST http://localhost:5000/api/loop/initiate-payment \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "254105087393",
    "amount": 100,
    "description": "Test Payment"
  }'
```

---

## 🔌 API Endpoints

### **Initiate Payment**
```
POST /api/loop/initiate-payment
Content-Type: application/json

{
  "phone": "254105087393",      // Required: M-Pesa number
  "amount": 100,                // Required: Amount in KSh
  "description": "Service",     // Optional: Payment description
  "till": "472042",             // Optional: Merchant till
  "reference": "STC-..."        // Optional: Custom reference
}

Response:
{
  "success": true,
  "message": "M-Pesa prompt sent successfully",
  "reference": "STC-20260818-ABC123",
  "phone": "254105087393",
  "amount": 100
}
```

### **Check Payment Status**
```
GET /api/loop/status/{reference}

Example: http://localhost:5000/api/loop/status/STC-20260818-ABC123

Response:
{
  "reference": "STC-20260818-ABC123",
  "status": "initiated|pending|completed|failed",
  "amount": 100,
  "phone": "254105087393",
  "initiated_at": "2026-08-18T11:10:12Z"
}
```

### **Webhook Callback** (LOOP → Your Server)
```
POST /api/loop/callback
Authorization: Bearer {signature}
Content-Type: application/json

{
  "reference": "STC-20260818-ABC123",
  "status": "completed",
  "amount": 100,
  "phone": "254105087393",
  "transaction_id": "LOP123456"
}
```

### **Health Check**
```
GET /api/health

Response:
{
  "status": "ok",
  "merchant_till": "472042",
  "mode": "sandbox",
  "timestamp": "2026-08-18T11:10:12Z"
}
```

### **View Transactions** (Admin - Development Only)
```
GET /api/admin/transactions

Response:
{
  "total": 5,
  "transactions": {
    "STC-20260818-ABC123": {
      "reference": "STC-20260818-ABC123",
      "amount": 100,
      "phone": "7393",
      "status": "completed",
      "initiated_at": "2026-08-18T11:10:12Z"
    }
  }
}
```

---

## 🔗 Frontend Integration

The `index.html` frontend is already configured to call your backend:

```javascript
// Payment form automatically posts to:
fetch("/api/loop/initiate-payment", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({
    phone: "254105087393",
    amount: 1000,
    description: "Service Payment"
  })
})
```

**Features:**
- ✅ Automatic phone number normalization (07... → 254...)
- ✅ Configurable retry attempts (1-5)
- ✅ Exponential backoff delays (3s, 6s, 9s)
- ✅ Real-time toast notifications
- ✅ Modal status updates

---

## 🔒 Configure LOOP Callback Webhook

After deploying your backend online, tell LOOP where to send payment confirmations:

1. Go to **LOOP Business Dashboard** → **Settings → Webhooks** or **Callback URLs**
2. Enter your server URL:
   ```
   https://yourdomain.com/api/loop/callback
   ```
3. LOOP will POST payment confirmations to this endpoint
4. Your server validates the signature and updates order status

**Example webhook call from LOOP:**
```bash
POST https://yourdomain.com/api/loop/callback
Authorization: Bearer {hmac_signature}
Content-Type: application/json

{
  "reference": "STC-20260818-ABC123",
  "status": "completed",
  "amount": 1000,
  "phone": "254105087393"
}
```

---

## 🧪 Testing Flow

### **Sandbox Testing Steps:**

1. **Start backend:**
   ```bash
   python app.py
   ```

2. **Open frontend:**
   - Open `index.html` in a browser
   - Go to **Payment** section

3. **Initiate payment:**
   - Enter phone: `254105087393` (or any test number)
   - Enter amount: `100`
   - Click "Send M-Pesa prompt"

4. **Monitor logs:**
   ```
   INFO:__main__:Initiating LOOP payment: STC-260818-ABC123, 100 KSh to 254105087393
   INFO:__main__:LOOP Response Status: 200
   INFO:__main__:✓ Payment initiated: STC-260818-ABC123
   ```

5. **Check status:**
   ```bash
   curl http://localhost:5000/api/loop/status/STC-260818-ABC123
   ```

6. **Simulate callback** (for testing):
   ```bash
   curl -X POST http://localhost:5000/api/loop/callback \
     -H "Authorization: Bearer {signature}" \
     -H "Content-Type: application/json" \
     -d '{
       "reference": "STC-260818-ABC123",
       "status": "completed",
       "amount": 100,
       "phone": "254105087393"
     }'
   ```

---

## 📦 Production Deployment

### **Before Going Live:**

1. **Update LOOP_CONFIG in app.py:**
   ```python
   "PROMPT_URL": "https://api.loop.co.ke/gateway/mpesa-prompt/2.0/services/process-request"
   ```

2. **Switch to production credentials:**
   - Get live `SECRET_KEY` from LOOP
   - Verify merchant till is correct

3. **Enable HTTPS:**
   - Your frontend and backend must use HTTPS
   - LOOP requires secure connections

4. **Add Authentication:**
   - Protect `/api/admin/transactions` endpoint
   - Use API keys or JWT tokens

5. **Database Integration:**
   - Replace in-memory `transactions` dict with a real database
   - Store payment records persistently
   - Implement proper error logging

6. **Email/SMS Notifications:**
   - Send order confirmation to customer
   - Send payment receipt on callback
   - Notify admin of successful payments

7. **Whitelist LOOP IPs:**
   - Add LOOP's IP addresses to your firewall if needed
   - Verify with LOOP support

---

## 🐛 Troubleshooting

### **"Authorization failed" error:**
- ❌ Wrong `SECRET_KEY` in LOOP_CONFIG
- ✅ Copy directly from LOOP Dashboard
- ✅ Check for extra spaces or special characters

### **"Invalid phone format" error:**
- ❌ Phone not starting with 254
- ✅ Use format: `254105087393`
- ✅ Or `0105087393` (auto-converted)

### **"Payment gateway timeout":**
- ❌ LOOP API is slow or down
- ✅ Check LOOP status page
- ✅ Retry with exponential backoff (already built in)

### **"Cannot reach payment gateway":**
- ❌ Network issue or LOOP API is unreachable
- ✅ Check internet connection
- ✅ Verify LOOP_URL is correct
- ✅ Check firewall rules

### **Callback not received:**
- ❌ Webhook URL not configured in LOOP Dashboard
- ❌ Server is not accessible from internet
- ❌ LOOP cannot reach your domain
- ✅ Configure webhook in LOOP Business Dashboard
- ✅ Use ngrok for testing: `ngrok http 5000`

---

## 📚 References

- **LOOP Documentation**: https://loop.co.ke/developers
- **LOOP Business Dashboard**: https://business.loop.co.ke
- **LOOP Support**: support@loop.co.ke
- **Flask Documentation**: https://flask.palletsprojects.com/

---

## 📝 File Structure

```
siniora-tech-cyber2/
├── index.html              # Frontend portal with payment UI
├── app.py                  # Flask backend with LOOP integration
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── README.md              # This file
└── .gitignore             # Git ignore file
```

---

## ⚠️ Security Notes

1. **Never commit `.env` or credentials to GitHub:**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Use environment variables for production:**
   ```python
   import os
   SECRET_KEY = os.getenv('LOOP_SECRET_KEY')
   ```

3. **Always validate signatures** on incoming webhooks

4. **Use HTTPS only** in production

5. **Limit admin endpoints** with authentication

6. **Log transactions** for audit trails

---

## 🎯 Next Steps

1. ✅ Get LOOP credentials
2. ✅ Update `app.py` with your SECRET_KEY
3. ✅ Run backend: `python app.py`
4. ✅ Test with `curl` or Postman
5. ✅ Deploy to production server
6. ✅ Configure webhook in LOOP Dashboard
7. ✅ Test end-to-end payment flow

---

**Need help?** Check the inline comments in `app.py` or contact LOOP support.

**Questions?** Create an issue on GitHub: https://github.com/sinioratech/siniora-tech-cyber2
