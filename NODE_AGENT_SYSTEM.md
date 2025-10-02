# Node Agent System Documentation

## Overview
The Node Agent System enables the Alterion Panel to monitor and manage both the local panel server and multiple remote servers/websites through a unified dropdown interface.

## Architecture

### 1. Server Selection Endpoint
**Endpoint:** `/api/dashboard/alterion/panel/server/available-servers`

Returns a unified list containing:
- **Local Panel Server:** Named "Server {server_id}" with type `local`
- **Remote Nodes:** All configured nodes with type `remote`

Each server entry includes:
- `id`: Unique identifier (e.g., "local-abc123" or "node-5")
- `name`: Display name
- `type`: "local" or "remote"
- `node_type`: "server", "website", "database", or "application"
- `hostname`: Server hostname
- `ip_address`: Server IP
- `status`: "online", "offline", "error", or "pending"
- `last_seen`: Last contact timestamp
- `is_local`: Boolean flag

### 2. Widget API Routing

#### Local Panel (Default)
When the local panel is selected, widgets fetch from:
```
/api/dashboard/alterion/panel/widget/{widget_type}
```

Examples:
- `/api/dashboard/alterion/panel/widget/alerts`
- `/api/dashboard/alterion/panel/widget/performance`
- `/api/dashboard/alterion/panel/widget/uptime`

#### Remote Nodes
When a remote node is selected, widgets fetch from:
```
/api/dashboard/alterion/panel/node/{node_id}/{widget_type}
```

Examples:
- `/api/dashboard/alterion/panel/node/5/alerts`
- `/api/dashboard/alterion/panel/node/5/performance`
- `/api/dashboard/alterion/panel/node/5/uptime`

### 3. Node Agent (node_agent.py)

The node agent is a Python CLI tool deployed to remote servers at `/usr/local/bin/node_agent.py`.

#### Available Commands:
1. **collect_metrics** - Comprehensive system metrics collection
2. **system_info** - Hostname, platform, IP, boot time
3. **detect_services** - Checks for nginx, mysql, docker, postgresql, redis, mongodb
4. **list_files** - Directory listing with permissions
5. **read_file** - Read file contents
6. **check_nginx** - Test nginx configuration
7. **check_databases** - Detect MySQL/PostgreSQL versions
8. **check_firewall** - UFW/iptables/Windows Firewall status

#### Execution Method:
The panel connects to remote nodes via SSH:
```bash
ssh -i {auth_key} -p {port} {username}@{ip_address} \
  python3 /usr/local/bin/node_agent.py collect_metrics
```

Returns JSON response with metrics data.

### 4. Node Database Models

#### Node Model
Stores remote server connection info:
- Connection details (hostname, IP, port, SSH key)
- Authentication (username, auth_key path)
- Status tracking (online/offline/error/pending)
- Platform info (OS, version, architecture)
- Owner relationship (FK to User)

#### NodeMetrics Model
Historical metrics storage:
- CPU usage (percent, per-core data)
- Memory usage (used, total, percent, swap)
- Disk usage (JSON array of partitions)
- Network bytes (sent/received)
- Process count
- Full metrics JSON blob

#### NodeAlert Model
Alert records from nodes:
- Severity (critical/warning/info)
- Category (cpu/memory/disk/network/service)
- Message and details JSON
- Resolved status and timestamp
- Link to Node

#### NodeService Model
Detected services on nodes:
- Service type and name
- Running status
- Version info
- Configuration path

### 5. Node Management API

**Base URL:** `/api/services/nodes/`

#### Endpoints:
- `GET /` - List all nodes
- `POST /` - Create new node
- `GET /{id}/` - Get node details
- `PUT /{id}/` - Update node
- `DELETE /{id}/` - Delete node
- `POST /{id}/collect_metrics/` - Trigger metrics collection
- `GET /{id}/latest_metrics/` - Get most recent metrics
- `GET /{id}/metrics_history/` - Get historical metrics (24h default)
- `GET /{id}/alerts/` - Get node alerts
- `GET /{id}/services/` - Get detected services
- `POST /{id}/list_files/` - List directory contents
- `POST /{id}/read_file/` - Read file content
- `GET /{id}/nginx_config/` - Check nginx configuration
- `GET /{id}/firewall_status/` - Get firewall status
- `POST /{id}/test_connection/` - Test SSH connection

## Frontend Implementation

### ServerSelector Component
**Location:** `frontend/src/components/ServerSelector.jsx`

Features:
- Fetches from `/api/dashboard/alterion/panel/server/available-servers`
- Dropdown displays all servers (local + remote)
- Shows status indicator (online/offline/error/pending)
- Shows node type (Server/Website/Database/Application)
- Displays last seen timestamp
- Refresh button to reload server list
- Search functionality
- "Add Server" button

### Widget Integration
**Location:** Each widget in `frontend/src/components/widgets/`

Pattern:
```jsx
const MyWidget = ({ selectedNode, ...props }) => {
  const fetchData = async () => {
    // Determine API endpoint based on selected node
    let apiUrl = '/api/dashboard/alterion/panel/widget/mydata';
    
    if (selectedNode && selectedNode.type === 'remote' && selectedNode.node_id) {
      apiUrl = `/api/dashboard/alterion/panel/node/${selectedNode.node_id}/mydata`;
    }
    
    const response = await axios.get(apiUrl);
    // ... handle response
  };
  
  useEffect(() => {
    fetchData();
  }, [selectedNode]); // Refetch when node changes
  
  // ... render widget
};
```

## Setup Instructions

### 1. Add a New Remote Node

1. SSH into the remote server
2. Copy `node_agent.py` to `/usr/local/bin/`:
   ```bash
   scp node_agent.py user@remote:/usr/local/bin/
   chmod +x /usr/local/bin/node_agent.py
   ```

3. Install dependencies on remote server:
   ```bash
   pip3 install psutil
   ```

4. Generate SSH key pair for authentication:
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/alterion_node_key
   ssh-copy-id -i ~/.ssh/alterion_node_key.pub user@remote
   ```

5. Create Node in panel:
   - Go to node management page
   - Click "Add Server"
   - Fill in details:
     - Name: "Production Server"
     - Hostname: server.example.com
     - IP: 192.168.1.100
     - Port: 22
     - Username: your_user
     - SSH Key: Upload private key
     - Node Type: server/website/database/application
   - Click "Test Connection"
   - Save

### 2. Access Remote Node Data

1. Open dashboard
2. Click server dropdown (top left)
3. Select remote node from list
4. All widgets automatically fetch data from selected node
5. Alerts, performance, uptime, etc. show remote server metrics

### 3. Manage Nodes

**Node List Page:**
- View all nodes with status
- Last seen timestamp
- Quick actions (edit, delete, test connection)

**Node Detail Page:**
- Real-time metrics dashboard
- Historical metrics charts
- Active alerts list
- Detected services
- File browser
- Configuration management

## Security Considerations

1. **SSH Key Authentication:** Nodes use SSH keys, never passwords
2. **User Isolation:** Each user only sees their own nodes
3. **Command Whitelist:** Node agent only accepts predefined commands
4. **Path Restrictions:** File operations limited to safe directories
5. **Timeout Protection:** All SSH operations have 30s timeout
6. **Connection Status:** Nodes marked offline if unreachable

## Troubleshooting

### Node Shows as Offline
1. Check SSH connectivity: `ssh -i key user@host`
2. Verify node_agent.py exists: `ls /usr/local/bin/node_agent.py`
3. Check Python 3 installed: `python3 --version`
4. Test agent manually: `python3 /usr/local/bin/node_agent.py system_info`

### Widget Shows "Failed to Load"
1. Check browser console for API errors
2. Verify node status is "online"
3. Check backend logs for SSH errors
4. Test node connection from panel

### High Latency on Remote Nodes
1. Check network connectivity to node
2. Verify node resources aren't exhausted
3. Consider increasing SSH timeout
4. Review metrics collection frequency

## Future Enhancements

- [ ] Real-time websocket metrics streaming
- [ ] Node agent auto-update system
- [ ] Multi-node aggregate views
- [ ] Alert correlation across nodes
- [ ] Automated node discovery
- [ ] Configuration deployment system
- [ ] Backup management
- [ ] Log aggregation
- [ ] Custom metric collection
- [ ] Node grouping/tagging
