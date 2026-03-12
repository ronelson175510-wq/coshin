/**
 * Coshin.com API Client
 * Replaces Firebase with MySQL backend API calls.
 */

// Priority order:
// 1. Custom URL from localStorage (settings page)
// 2. Same-origin '/api' when frontend is on a hosted domain
// 3. Local/LAN fallback for development
let API_BASE_URL;

function normalizeApiBaseUrl(url) {
  if (!url) return '';
  let cleaned = url.trim();
  if (!cleaned) return '';

  // Accept host-only values (e.g. localhost:5000, api.example.com) from settings.
  if (!/^https?:\/\//i.test(cleaned)) {
    if (cleaned.startsWith('/')) {
      cleaned = `${window.location.origin}${cleaned}`;
    } else if (/^(localhost|127\.0\.0\.1|\d{1,3}(?:\.\d{1,3}){3})(:\d+)?(\/|$)/i.test(cleaned)) {
      cleaned = `http://${cleaned}`;
    } else if (/^[a-z0-9.-]+\.[a-z]{2,}(:\d+)?(\/|$)/i.test(cleaned)) {
      cleaned = `https://${cleaned}`;
    }
  }

  try {
    const parsed = new URL(cleaned);
    const normalizedPath = parsed.pathname.replace(/\/$/, '');
    parsed.pathname = normalizedPath.toLowerCase().endsWith('/api') ? normalizedPath : `${normalizedPath}/api`;
    return parsed.toString().replace(/\/$/, '');
  } catch {
    return '';
  }
}

if (typeof window !== 'undefined' && window.location) {
  // Check if user has configured a custom API URL in settings
  const customUrl = localStorage.getItem('customApiUrl');
  const normalizedCustomUrl = normalizeApiBaseUrl(customUrl || '');

  if (normalizedCustomUrl) {
    API_BASE_URL = normalizedCustomUrl;
  } else {
    // Remove malformed custom URLs so they cannot keep breaking auth requests.
    if (customUrl) {
      localStorage.removeItem('customApiUrl');
    }

    // Default to backend running on port 8080 for local development
    API_BASE_URL = normalizeApiBaseUrl('http://127.0.0.1:8080/api');
  }

  // Expose resolved base URL so pages can reuse the same API endpoint.
  window.COSHIN_API_BASE_URL = API_BASE_URL;
}

class CoshinAPIClient {
  constructor() {
    this.token = localStorage.getItem('authToken');
    this.currentUser = this.parseStoredJson('currentUser', null);
  }

  // ============================================
  // HELPERS
  // ============================================

  getHeaders(includeAuth = true) {
    const headers = {
      'Content-Type': 'application/json'
    };
    
    if (includeAuth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    
    return headers;
  }

  parseStoredJson(key, fallback = null) {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;

    try {
      return JSON.parse(raw);
    } catch {
      localStorage.removeItem(key);
      return fallback;
    }
  }

  async request(endpoint, options = {}) {
    try {
      const headers = {
        ...this.getHeaders(options.requiresAuth !== false),
        ...(options.headers || {})
      };

      // ngrok free domains may show a browser warning page unless this header is set.
      if (API_BASE_URL && API_BASE_URL.includes('ngrok')) {
        headers['ngrok-skip-browser-warning'] = 'true';
      }

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers
      });

      const rawBody = await response.text();
      let data;

      try {
        data = rawBody ? JSON.parse(rawBody) : {};
      } catch {
        // If upstream returns HTML/plain text, surface a useful error instead of a JSON parse crash.
        const looksLikeHtml = rawBody.trim().startsWith('<');
        const nonJsonMessage = looksLikeHtml
          ? 'Server returned HTML instead of API JSON. Verify API URL in Settings and ngrok tunnel status.'
          : `Server returned an invalid response: ${rawBody.slice(0, 120)}`;
        throw new Error(nonJsonMessage);
      }

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      return data;
    } catch (error) {
      // Enhanced error handling
      let friendlyMessage = error.message;
      
      if (error.message === 'Failed to fetch') {
        friendlyMessage = `Cannot reach server at ${API_BASE_URL}. Please check:\n- Phone is on same WiFi network (${API_BASE_URL})\n- Firewall is not blocking port 5000\n- Computer and phone have network connectivity`;
      } else if (error.message && error.message.toLowerCase().includes('expected pattern')) {
        friendlyMessage = 'Invalid API URL format in settings. Please open Settings and save a valid server URL.';
      } else if (error.message.includes('network')) {
        friendlyMessage = 'Network connection error. Check your WiFi connection.';
      }
      
      console.error('API Error:', error);
      console.error('Attempted URL:', `${API_BASE_URL}${endpoint}`);
      throw new Error(friendlyMessage);
    }
  }

  saveAuth(token, user) {
    this.token = token;
    this.currentUser = user;
    localStorage.setItem('authToken', token);
    localStorage.setItem('currentUser', JSON.stringify(user));
  }

  clearAuth() {
    this.token = null;
    this.currentUser = null;
    localStorage.removeItem('authToken');
    localStorage.removeItem('currentUser');
  }

  isAuthenticated() {
    return !!this.token && !!this.currentUser;
  }

  getCurrentUser() {
    return this.currentUser;
  }

  // ============================================
  // AUTHENTICATION
  // ============================================

  async signup(email, password, username) {
    const data = await this.request('/auth/signup', {
      method: 'POST',
      requiresAuth: false,
      body: JSON.stringify({ email, password, username })
    });

    this.saveAuth(data.token, data.user);
    return data;
  }

  async login(email, password) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      requiresAuth: false,
      body: JSON.stringify({ email, password })
    });

    this.saveAuth(data.token, data.user);
    return data;
  }

  logout() {
    this.clearAuth();
    window.location.href = 'login.html';
  }

  // ============================================
  // PROFILE
  // ============================================

  async getProfile() {
    return await this.request('/profile');
  }

  async updateProfile(profileData) {
    return await this.request('/profile', {
      method: 'PUT',
      body: JSON.stringify(profileData)
    });
  }

  // ============================================
  // PHOTOS
  // ============================================

  async uploadPhoto(title, description, photoDataURL, allowGifts = true) {
    const profilePicture = localStorage.getItem('profilePicture') || '';
    return await this.request('/photos', {
      method: 'POST',
      body: JSON.stringify({
        title,
        description,
        photo: photoDataURL,  // Base64 encoded
        profile_picture: profilePicture,
        allow_gifts: Boolean(allowGifts)
      })
    });
  }

  async getPhotos() {
    return await this.request('/photos');
  }

  async getPhotoImage(photoId) {
    return await this.request(`/photos/${photoId}`, {
      requiresAuth: false
    });
  }

  async deletePhoto(photoId) {
    return await this.request(`/photos/${photoId}`, {
      method: 'DELETE'
    });
  }

  // ============================================
  // VIDEOS
  // ============================================

  async uploadVideo(title, description, videoDataURL, allowGifts = true) {
    const profilePicture = localStorage.getItem('profilePicture') || '';
    return await this.request('/videos', {
      method: 'POST',
      body: JSON.stringify({
        title,
        description,
        video: videoDataURL,  // Base64 encoded
        profile_picture: profilePicture,
        allow_gifts: Boolean(allowGifts)
      })
    });
  }

  async getVideos() {
    return await this.request('/videos');
  }

  async deleteVideo(videoId) {
    return await this.request(`/videos/${videoId}`, {
      method: 'DELETE'
    });
  }

  // ============================================
  // POSTS
  // ============================================

  async createPost(title, content, allowGifts = true) {
    const profilePicture = localStorage.getItem('profilePicture') || '';

    return await this.request('/posts', {
      method: 'POST',
      body: JSON.stringify({
        title,
        content,
        profile_picture: profilePicture,
        allow_gifts: Boolean(allowGifts)
      })
    });
  }

  // ============================================
  // GIFTS
  // ============================================

  async sendGift(contentType, contentId, giftName, giftIcon, giftPrice = 0) {
    return await this.request('/gifts', {
      method: 'POST',
      body: JSON.stringify({
        content_type: contentType,
        content_id: contentId,
        gift_name: giftName,
        gift_icon: giftIcon,
        gift_price: giftPrice
      })
    });
  }

  async getGiftsCount(contentType, contentId) {
    return await this.request(`/gifts-count/${contentType}/${contentId}`, {
      requiresAuth: false
    });
  }

  async getPosts() {
    return await this.request('/posts');
  }

  async deletePost(postId) {
    return await this.request(`/posts/${postId}`, {
      method: 'DELETE'
    });
  }

  // ============================================
  // LIKES
  // ============================================

  async addLike(contentType, contentId) {
    return await this.request('/likes', {
      method: 'POST',
      body: JSON.stringify({
        content_type: contentType,
        content_id: contentId
      })
    });
  }

  async removeLike(contentType, contentId) {
    return await this.request(`/likes/${contentType}/${contentId}`, {
      method: 'DELETE'
    });
  }

  async checkLike(contentType, contentId) {
    return await this.request(`/likes/${contentType}/${contentId}/check`);
  }

  async getLikesCount(contentType, contentId) {
    return await this.request(`/likes-count/${contentType}/${contentId}`, {
      requiresAuth: false
    });
  }

  // ============================================
  // COMMENTS
  // ============================================

  async addComment(contentType, contentId, comment) {
    return await this.request('/comments', {
      method: 'POST',
      body: JSON.stringify({
        content_type: contentType,
        content_id: contentId,
        comment
      })
    });
  }

  async getComments(contentType, contentId) {
    return await this.request(`/comments/${contentType}/${contentId}`, {
      requiresAuth: false
    });
  }

  async deleteComment(commentId) {
    return await this.request(`/comments/${commentId}`, {
      method: 'DELETE'
    });
  }

  // ============================================
  // FEED
  // ============================================

  async getFeed() {
    return await this.request('/feed');
  }

  // ============================================
  // MESSAGES
  // ============================================

  async getMessageConversations() {
    return await this.request('/messages/conversations');
  }

  async getMessageThread(partnerId) {
    return await this.request(`/messages/${partnerId}`);
  }

  async sendMessage(receiverId, message) {
    return await this.request('/messages', {
      method: 'POST',
      body: JSON.stringify({ receiver_id: receiverId, message })
    });
  }

  async deleteMessage(messageId) {
    return await this.request(`/messages/${messageId}`, {
      method: 'DELETE'
    });
  }

  async discoverUsers(query = '', limit = 50) {
    const q = encodeURIComponent(query || '');
    const safeLimit = Math.max(1, Math.min(Number(limit) || 50, 100));
    return await this.request(`/users/discover?q=${q}&limit=${safeLimit}`, {
      requiresAuth: false
    });
  }

  // ============================================
  // SEARCH FUNCTIONALITY
  // ============================================

  async searchProducts(query = '', limit = 10) {
    const q = encodeURIComponent(query || '');
    const safeLimit = Math.max(1, Math.min(Number(limit) || 10, 50));
    return await this.request(`/products/search?q=${q}&limit=${safeLimit}`, {
      requiresAuth: false
    });
  }

  async searchUsers(query = '', limit = 10) {
    const q = encodeURIComponent(query || '');
    const safeLimit = Math.max(1, Math.min(Number(limit) || 10, 50));
    return await this.request(`/users/search?q=${q}&limit=${safeLimit}`, {
      requiresAuth: false
    });
  }

  async searchPosts(query = '', limit = 10) {
    const q = encodeURIComponent(query || '');
    const safeLimit = Math.max(1, Math.min(Number(limit) || 10, 50));
    return await this.request(`/posts/search?q=${q}&limit=${safeLimit}`, {
      requiresAuth: false
    });
  }

  // ============================================
  // NOTIFICATIONS
  // ============================================

  async getNotifications() {
    return await this.request('/notifications');
  }

  async getUnreadNotificationsCount() {
    return await this.request('/notifications/unread-count');
  }

  async createNotification(toUserId, type, data = {}) {
    return await this.request('/notifications', {
      method: 'POST',
      body: JSON.stringify({
        to_user_id: toUserId,
        type: type,
        content_type: data.contentType || '',
        content_id: data.contentId || 0,
        action_data: JSON.stringify(data.actionData || {})
      })
    });
  }

  async markNotificationRead(notificationId) {
    return await this.request(`/notifications/${notificationId}/read`, {
      method: 'PUT'
    });
  }

  async markAllNotificationsRead() {
    return await this.request('/notifications/mark-all-read', {
      method: 'PUT'
    });
  }

  async deleteNotification(notificationId) {
    return await this.request(`/notifications/${notificationId}`, {
      method: 'DELETE'
    });
  }

  async clearAllNotifications() {
    return await this.request('/notifications/clear-all', {
      method: 'DELETE'
    });
  }

  // ============================================
  // HEALTH CHECK
  // ============================================

  async healthCheck() {
    return await this.request('/health', {
      requiresAuth: false
    });
  }
}

// Create global instance
const coshinAPI = new CoshinAPIClient();
if (typeof window !== 'undefined') {
  window.coshinAPI = coshinAPI;
}

window.addEventListener('DOMContentLoaded', () => {
  const publicPages = [
    'login.html',
    'signup.html',
    'settings.html',
    'termsandcontitions.html',
    'privacy-policy.html',
    'coshinmarketpolicies.html',
    'coshinmarket.html',
    'coshinsellerplan.html'
  ];
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  const currentAuthUser = coshinAPI.getCurrentUser ? coshinAPI.getCurrentUser() : null;
  
  // Only force profile setup if explicitly marked as needing it (first-time signup)
  // Don't force it based on missing profile_picture alone - that's not user-friendly for existing users
  const needsProfileSetup = localStorage.getItem('needsProfileSetup') === 'true';

  // Enforce first-time profile setup before accessing the app.
    // TEMPORARY: Disable login enforcement for development
    /*
    if (
      coshinAPI.isAuthenticated() &&
      needsProfileSetup &&
      currentPage !== 'profile-setup.html'
    ) {
      window.location.href = 'profile-setup.html';
      return;
    }

    if (publicPages.includes(currentPage)) {
      return;
    }

    if (!coshinAPI.isAuthenticated()) {
      const returnTo = encodeURIComponent(currentPage);
      window.location.href = `login.html?returnTo=${returnTo}`;
    }
    */
});
