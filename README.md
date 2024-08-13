# Project Panthera 🐆

![Project Status](https://img.shields.io/badge/status-active-brightgreen)
[![Open Issues](https://gitchrisqueen.github.io/panthera/badges/open_issues.svg)](https://github.com/gitchrisqueen/panthera/issues?q=sort%3Aupdated-desc+is%3Aissue+is%3Aopen)
[![Closed Issues](https://gitchrisqueen.github.io/panthera/badges/closed_issues.svg)](https://github.com/gitchrisqueen/panthera/issues?q=sort%3Aupdated-desc+is%3Aissue+is%3Aclosed)
[![CI Build](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml/badge.svg)](https://github.com/gitchrisqueen/panthera/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue)

Welcome to **Project Panthera**, a cutting-edge Sports Betting Analysis Application designed as a Software-as-a-Service (SaaS) platform. This application leverages real-time data, historical analysis, and automation to provide users with informed betting decisions.

## 📚 Documentation

All project documentation can be found in the [`docs`](https://github.com/gitchrisqueen/panthera/tree/main/docs) directory. Below are the key documents that provide in-depth details on the project:

- [Code Requirements](https://github.com/gitchrisqueen/panthera/blob/main/docs/code-requirements.md): Detailed technical specifications for the application.
- [Project Plan](https://github.com/gitchrisqueen/panthera/blob/main/docs/project-plan.md): Breakdown of the project milestones, tasks, and estimated hours.
- [Project Summary](https://github.com/gitchrisqueen/panthera/blob/main/docs/project-summary.md): Overview of the product, target audience, and estimated project duration.
- [Sports Betting Process](https://github.com/gitchrisqueen/panthera/blob/main/docs/sports_betting_process.md): Comprehensive guide to the sports betting analysis process that drives the app.

## 🔑 Key Elements

- [Getting Started](#-getting-started)
- [Development Workflow](#%EF%B8%8F-development-workflow)
- [Features](#-features)
- [Contributing](#-contributing)
- [Stakeholders and Investors](#-stakeholders-and-investors)
- [License and Contact](#-license)

## 🚀 Getting Started

### Prerequisites

To run this project locally, you'll need to have the following installed:

- Node.js and npm
- Python (v3.8 or higher)
- Docker
- Git

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/gitchrisqueen/panthera.git
   cd panthera
   ```

2. **Configure environment variables:**
   - Create a `.env` file in both `backend` and `frontend` directories and fill in the necessary environment variables as described in the respective `env.example` files.


3. **Start The application:**

   **Start Using Docker:**
      ```bash
      ./scripts/start_docker.sh 
      ```

   **or Start Locally:**
      ```bash
      ./scripts/start.sh
      ```


## 🛠️ Development Workflow

We follow Agile methodologies, with a focus on iterative development and regular feedback loops. Our ticketing system is managed via [GitHub Issues](https://github.com/gitchrisqueen/panthera/issues) and [Projects](https://github.com/gitchrisqueen/panthera/projects).

### Continuous Integration

Our CI pipeline is set up to automatically run tests and deploy to a staging environment. You can check the CI build status at any time via the badge above.

### Branching Strategy

- **`main`**: Production-ready code.
- **`dev`**: Active development branch.
- **Feature branches**: Create a new branch for each feature or bugfix, e.g., `feature/user-auth`.

### Submitting a Pull Request

1. Ensure your code adheres to the coding standards described in the [Code Requirements](https://github.com/gitchrisqueen/panthera/blob/main/docs/code-requirements.md).
2. Run all tests locally before submitting.
3. Submit your PR to the `dev` branch.
4. Add descriptive comments and link to the relevant issue or ticket.

## 💡 Features

- **Real-time Data Integration**: Seamless integration with external APIs for up-to-the-minute betting lines and game statistics.
- **Customizable Dashboards**: Tailor your user experience with customizable views and alerts.
- **Historical Data Analysis**: Access and analyze past game data to make data-driven betting decisions.
- **Automated Alerts**: Set and receive alerts for specific conditions, like line movements or game starts.

## 🧑‍💻 Contributing

We welcome contributions from the community! Please refer to the [Contributing Guidelines](CONTRIBUTING.md) for more details.

## 👥 Stakeholders and Investors

This project is an exciting opportunity for stakeholders and investors interested in the growing sports betting market. Project Panthera is designed to scale and adapt, providing value to a wide range of users.

For business inquiries, please contact [Chris Queen](mailto:chris@christopherqueenconsulting.com).

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

For any questions, issues, or contributions, please reach out via [GitHub Issues](https://github.com/gitchrisqueen/panthera/issues) or contact the project lead directly at [Chris Queen](mailto:chris@yourcompany.com).
