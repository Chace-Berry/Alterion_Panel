# 🤝 Contributing to Alterion Panel

Thank you for your interest in contributing to Alterion Panel! We welcome contributions from the community to help improve and expand this web-based server management platform.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)
- [Documentation](#documentation)

## 📜 Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors. By participating, you agree to:

- Be respectful and inclusive
- Focus on constructive feedback
- Accept responsibility for mistakes
- Show empathy towards other contributors
- Help create a positive community

## 🚀 How to Contribute

There are many ways to contribute to Alterion Panel:

- **🐛 Bug Reports**: Report bugs and help us improve stability
- **✨ Feature Requests**: Suggest new features or enhancements
- **💻 Code Contributions**: Submit pull requests with fixes or new features
- **📚 Documentation**: Improve documentation, tutorials, or examples
- **🧪 Testing**: Help test new features and report issues
- **🌍 Translation**: Help translate the interface to other languages

## 🛠️ Development Setup

### Prerequisites

- **Docker & Docker Compose** (recommended for full setup)
- **Python 3.8+** (for backend development)
- **Git** (for version control)

### Quick Development Setup

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/Chace-Berry/Alterion_Panel.git
   cd Alterion_Panel
   ```

3. **Backend Development**
   ```bash
   cd backend/backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

   **Note:** Frontend development is currently disabled and will be re-enabled in a future update.

4. **Full Stack with Docker** (Recommended)
   ```bash
   cd docker
   docker-compose -f docker-compose.dev.yml up --build
   ```

### Environment Configuration

Create a `.env` file in the `backend/` directory:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379
```

## 🏗️ Project Structure

```
Alterion_Panel/
├── backend/                 # Django backend
│   ├── backend/            # Main Django project
│   ├── accounts/           # User management
│   ├── dashboard/          # Dashboard functionality
│   ├── services/           # Core services
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend (currently disabled)
├── docker/                # Docker configuration
│   ├── docker-compose.yml # Production setup
│   └── Dockerfile.*       # Container definitions
├── node_agent/           # Python monitoring agent
├── installer_react/      # Electron installer
├── nginx/               # Nginx configurations
└── docs/               # Documentation
```

## 💻 Coding Standards

### Backend (Python/Django)

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes
- Use meaningful variable and function names
- Keep functions small and focused (single responsibility)

### General Guidelines

- Write clear, concise commit messages
- Use descriptive branch names (`feature/add-user-auth`, `fix/login-bug`)
- Keep pull requests focused on a single feature or fix
- Add tests for new functionality
- Update documentation as needed

## 🧪 Testing

### Backend Testing

```bash
cd backend/backend
python manage.py test
```

### Docker Testing

```bash
cd docker
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## 📝 Submitting Changes

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clean, well-documented code
   - Add tests for new functionality
   - Ensure all tests pass
   - Update documentation if needed

3. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

4. **Push and Create Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a pull request on GitHub

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Include screenshots for UI changes
- Ensure CI checks pass
- Request review from maintainers

## 🐛 Reporting Issues

When reporting bugs, please include:

- **Clear Title**: Summarize the issue
- **Description**: Detailed steps to reproduce
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: OS, browser, versions
- **Screenshots**: If applicable
- **Logs**: Error messages or console output

## 📚 Documentation

- Keep code well-documented with comments
- Update README.md for significant changes
- Add examples for new features
- Maintain API documentation

## 🎯 Commit Message Format

We follow conventional commit format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Testing
- `chore`: Maintenance

## 🙋 Getting Help

- [GitHub Issues](https://github.com/Chace-Berry/Alterion_Panel/issues): For bugs and feature requests
- [GitHub Discussions](https://github.com/Chace-Berry/Alterion_Panel/discussions): For questions and general discussion
- **Email**: chaceberry686@gmail.com for direct contact

## 📄 License

By contributing to Alterion Panel, you agree that your contributions will be licensed under the same license as the project (APUL).

---

Thank you for contributing to Alterion Panel! 🚀</content>
