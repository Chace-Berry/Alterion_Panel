<div align="center">
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logo-01.png?v=1">
        <source media="(prefers-color-scheme: light)" srcset="assets/logo-02.png?v=1">
        <img alt="Alterion Logo" src="assets/logo-02.png?v=1" width="400">
    </picture>
</div>

<div align="center">

[![License: APUL](https://img.shields.io/badge/License-APULv2-blue.svg)](/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13.2-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2.6-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-4.53.0-2496ED?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Version](https://img.shields.io/badge/version-0.2.2--beta-blue.svg)](.)


_A modern, open-source web hosting control panel — manage servers, websites, users, and SSL certificates with ease. Built on a Django REST API backend and a React frontend, and ready for containerized deployment with Docker._

---
</div>
A comprehensive web-based control panel for managing and monitoring servers, nodes, and applications. Built with Django backend and React frontend, Alterion Panel provides a unified interface for system administration, deployment, and monitoring tasks.

## 🎯 Features

Alterion Panel offers a wide range of features for server management:

### Core Functionality
- **Authentication & Access**: OAuth2 login with username/email/phone support
- **Dashboard & Widgets**: Customizable dashboard with alerts, uptime, performance, and activity widgets
- **Node Management**: SSH agent onboarding and WebSocket-based metrics API
- **Web-based Terminal**: Local PTY and remote SSH terminal access
- **File Manager**: SFTP integration with upload/download and file operations
- **Secret Manager**: Secure project/environment secrets with versioning

### Monitoring & Alerts
- **System Monitoring**: CPU, memory, disk, and process alerts
- **Uptime Monitoring**: Real-time checks with database history
- **Performance Metrics**: Agent-based metrics collection using psutil
- **Prometheus Integration**: Custom exporter with alert rules

### Deployment & Management
- **Service Management**: systemctl control for remote services
- **SSL Automation**: Let's Encrypt/Certbot integration
- **Background Jobs**: Celery workers for async tasks
- **Domain Management**: WHOIS lookup and DNS verification

### Additional Tools
- **Installer**: GUI installer with SSL, database, and superuser setup
- **Docker Support**: Containerized deployment options
- **Crypto Utilities**: Encrypted storage and key management

---

<div align="center">

**Support the development of Alterion Panel:**  
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-orange?logo=buymeacoffee&logoColor=white)](https://buymeacoffee.com/chaceberry)


</div>

---

## 📦 Installation

### Prerequisites
- Docker and Docker Compose
- (Optional for manual setup) Python 3.8+, Node.js 16+, PostgreSQL or SQLite, Redis

## 🚀 Quick Setup (Recommended)

Alterion Panel is designed for containerized deployment with Docker and Kubernetes. The easiest way to get started is using Docker Compose:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Chace-Berry/Alterion_Panel.git
   cd Alterion_Panel
   ```

2. **Run Docker Compose:**
   ```bash
   cd docker
   docker-compose up --build
   ```

   The panel will be available at `http://localhost:13527`

### Alternative: GUI Installer

For a user-friendly, guided setup experience, download and run the Alterion Webpanel Installer:

- Download the latest installer from the [Releases](https://github.com/Chace-Berry/Alterion_Panel/releases) page
- Run `Alterion.Webpanel.Installer.exe` (Windows) or the appropriate installer for your platform
- Follow the on-screen instructions for SSL setup, database configuration, and superuser creation

## Usage

### Accessing the Panel
- Open your browser and navigate to `http://localhost:13527` (Docker) Please not that apis require https so a reverse proxy with tls would be advised in this project we used nginx if you would like a free domain go and check out [Digital Plat Dev's free domains](https://github.com/DigitalPlatDev/FreeDomain)
- Log in with the superuser credentials you created during setup

### Key Workflows
1. **Add a Node**: Use the node onboarding feature to connect servers via SSH
2. **Monitor Systems**: View real-time metrics and alerts on the dashboard
3. **Manage Files**: Use the integrated file manager for SFTP operations
4. **Deploy Applications**: Utilize the page builder for no-code deployments
5. **Configure Services**: Control system services remotely


## 🌍 Support

- **Issues**: Report bugs and request features via [GitHub Issues](https://github.com/Chace-Berry/Alterion_Panel/issues)
- **Discussions**: Join community discussions on [GitHub Discussions](https://github.com/Chace-Berry/Alterion_Panel/discussions)
- **Email**: Contact the maintainer at [chaceberry686@gmail.com](mailto:chaceberry686@gmail.com)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on:

- Setting up a development environment
- Code style and standards
- Submitting pull requests
- Reporting issues

### Development Setup
1. Follow the installation steps above
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and test thoroughly
4. Submit a pull request

## 📄 License

This project is licensed under the Alterion Public Use License (APUL) - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with modern web technologies for efficient server management
- Special thanks to the open-source community

---

<div align="center">

**Made with ❤️ by Chace Berry**

**Support the project:**  
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-orange?logo=buymeacoffee&logoColor=white)](https://buymeacoffee.com/chaceberry)

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat&logo=discord&logoColor=white)](https://discord.com/invite/3gy9gJyJY8)
[![Website](https://img.shields.io/badge/Website-Coming%20Soon-blue?style=flat&logo=globe&logoColor=white)](.)
[![GitHub](https://img.shields.io/badge/GitHub-Chace--Berry-181717?style=flat&logo=github&logoColor=white)](https://github.com/Chace-Berry)

</div></content>

