# Widget API Endpoints Documentation

## Base URL
All widget endpoints are prefixed with: `/api/alterion/panel/widget/`

## Authentication
All endpoints require authentication using `CookieOAuth2Authentication`

---

## Endpoints

### 1. Alerts Widget
**Endpoint:** `GET /api/alterion/panel/widget/alerts`

**Response:**
```json
{
  "alerts": [
    {
      "id": 1,
      "type": "critical|warning|info",
      "message": "Alert message",
      "timestamp": "2025-10-01T15:00:00Z",
      "resolved": false
    }
  ]
}
```

---

### 2. Traffic Widget
**Endpoint:** `GET /api/alterion/panel/widget/traffic`

**Response:**
```json
{
  "current_visitors": 250,
  "today_visitors": 3500,
  "today_pageviews": 15000,
  "trend": "up",
  "chart_data": [
    {"time": "00:00", "visitors": 45},
    {"time": "04:00", "visitors": 20}
  ]
}
```

---

### 3. Uptime Monitor Widget
**Endpoint:** `GET /api/alterion/panel/widget/uptime`

**Response:**
```json
{
  "uptime_percentage": 99.98,
  "current_status": "online",
  "last_downtime": "2025-09-24T10:00:00Z",
  "response_time": 125,
  "incidents_30d": 1
}
```

---

### 4. Performance Metrics Widget
**Endpoint:** `GET /api/alterion/panel/widget/performance`

**Response:**
```json
{
  "cpu_usage": 45,
  "memory_usage": 68,
  "disk_usage": 52,
  "network_in": 450,
  "network_out": 250,
  "load_average": 1.85
}
```

---

### 5. Quick Actions Widget
**Endpoint:** `GET /api/alterion/panel/widget/quick-actions`

**Response:**
```json
{
  "actions": [
    {
      "id": "restart_server",
      "label": "Restart Server",
      "icon": "power"
    }
  ]
}
```

**Execute Action:** `POST /api/alterion/panel/widget/quick-actions`

**Request Body:**
```json
{
  "action_id": "restart_server"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Action restart_server executed successfully"
}
```

---

### 6. Recent Activity Widget
**Endpoint:** `GET /api/alterion/panel/widget/activity`

**Response:**
```json
{
  "activities": [
    {
      "id": 1,
      "type": "deployment|security|backup|user",
      "description": "Deployed version 2.1.0 to production",
      "user": "admin",
      "timestamp": "2025-10-01T14:45:00Z"
    }
  ]
}
```

---

### 7. Domain Expiry Widget
**Endpoint:** `GET /api/alterion/panel/widget/domains`

**Response:**
```json
{
  "domains": [
    {
      "domain": "example.com",
      "expiry_date": "2025-11-15T00:00:00Z",
      "days_remaining": 45,
      "status": "ok|warning|critical",
      "registrar": "GoDaddy"
    }
  ]
}
```

---

## Testing Endpoints

You can test these endpoints using:

```bash
# Get alerts data
curl -X GET https://localhost:13527/api/alterion/panel/widget/alerts \
  -H "Cookie: your_auth_cookie"

# Get traffic data
curl -X GET https://localhost:13527/api/alterion/panel/widget/traffic \
  -H "Cookie: your_auth_cookie"

# Execute quick action
curl -X POST https://localhost:13527/api/alterion/panel/widget/quick-actions \
  -H "Cookie: your_auth_cookie" \
  -H "Content-Type: application/json" \
  -d '{"action_id": "clear_cache"}'
```

---

## Notes

- All timestamps are in ISO 8601 format
- Currently returning mock data - replace with actual database queries
- All endpoints require valid authentication cookies
- Response times should be < 200ms for optimal widget performance
