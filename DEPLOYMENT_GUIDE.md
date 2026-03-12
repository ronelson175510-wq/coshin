# Global Deployment Guide for Coshin.com

This guide will help you deploy Coshin.com globally so users can access it from anywhere.

## Option A: Deploy to Render (Recommended - Free tier available)

### Backend Deployment:

1. **Sign up at https://render.com**

2. **Push your code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

3. **Create a new Web Service on Render:**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
   - Set environment variables in Render's dashboard:
     - `DB_HOST`: Your database host
     - `DB_USER`: root
     - `DB_PASSWORD`: Your database password
       - `DB_PORT`: 3306 (or provider port)
     - `DB_NAME`: Coshin
       - `DB_SSL_MODE`: required (if provider enforces TLS)

    Security checklist:
    - Never hardcode DB credentials in `app.py`
    - Store secrets only in Render/host environment variables
    - Keep `backend/.env` local only and out of version control

4. **Get your Render URL:** 
   - Example: `https://Coshin-backend.onrender.com`

### Frontend Configuration:

5. **Update API URL in coshin-api.js:**
   - Replace `'https://your-backend-url.com/api'` with your Render URL
   - Or add a settings page for users to configure the API endpoint

6. **Deploy frontend to Vercel/Netlify:**
   - Push frontend files to GitHub
   - Connect to Vercel: https://vercel.com/new
   - Deploy!

---

## Option B: Deploy to Heroku

1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli
2. **Login**: `heroku login`
3. **Create app**: `heroku create Coshin-backend`
4. **Add environment variables**: `heroku config:set DB_HOST=...`
5. **Deploy**: `git push heroku main`

---

## Option C: Deploy to AWS/DigitalOcean (Advanced)

For production-grade deployment with custom domain:
- AWS EC2 or DigitalOcean droplet
- Install Python, MySQL, Nginx
- Configure SSL certificate
- Set up auto-scaling

---

## Testing Globally Before Deploy:

**Use ngrok for FREE instant global access:**

```bash
# Install ngrok: https://ngrok.com/download
# Start your Flask server
python app.py

# In another terminal, expose it globally:
ngrok http 5000

# ngrok will give you: https://xxxxx.ngrok.io/api
# Use this URL in coshin-api.js for testing
```

---

## Database for Global Platform:

**For production, host your MySQL database on:**
- AWS RDS
- DigitalOcean Database
- Google Cloud SQL
- Azure Database for MySQL

This ensures database is accessible from your cloud backend.

---

## Steps to Go Live:

1. ✅ Update API URL in coshin-api.js
2. ✅ Add Procfile and gunicorn to requirements.txt
3. ✅ Push code to GitHub
4. ✅ Deploy backend to Render/Heroku
5. ✅ Move MySQL database to cloud (RDS, DigitalOcean, etc.)
6. ✅ Deploy frontend to Vercel/Netlify
7. ✅ Add custom domain
8. ✅ Enable HTTPS

Users can now log in from anywhere globally! 🌍
