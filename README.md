# FairHire-AI Phase 1

FairHire-AI is a SaaS-style resume intelligence and hiring bias analysis platform designed to bring transparency and equity to the recruitment process. By leveraging advanced AI analysis, it aims to uncover hidden biases in resume screening and Applicant Tracking Systems (ATS), empowering candidates with actionable insights to navigate the hiring landscape effectively.

This platform is a portfolio-grade, production-style system built to demonstrate engineering rigor and scalability, not for commercial use.

## Phase 1 Scope & Goals

The current phase focuses on establishing a robust, production-ready foundation for future development. This includes setting up the core infrastructure, implementing a scalable backend architecture, and creating a responsive frontend scaffold.

### Key Objectives:
-   **Infrastructure Setup:** Dockerized environment for seamless deployment and development.
-   **Backend Implementation:** High-performance API service using FastAPI and PostgreSQL.
-   **Frontend Development:** Next.js application structure ready for component integration.
-   **Production Readiness:** Adherence to best practices in code organization, security, and scalability.

## Architecture & Tech Stack

The system is architected as a modern monolith, designed for eventual microservices separation if needed.

-   **Backend:**
    -   **Framework:** FastAPI (Python) for high performance and async capabilities.
    -   **Database:** PostgreSQL for robust data persistence.
    -   **ORM:** SQLAlchemy / Pydantic for data modeling and validation.
-   **Frontend:**
    -   **Framework:** Next.js (TypeScript) for server-side rendering and static site generation.
    -   **Styling:** Tailwind CSS (planned) for utility-first styling.
-   **Infrastructure:**
    -   **Containerization:** Docker & Docker Compose for consistent environments.

## Local Development

### Prerequisites
-   Docker and Docker Compose
-   Node.js (optional, for local frontend runs)
-   Python 3.10+ (optional, for local backend runs)

### Quick Start with Docker (Recommended)
1.  Clone the repository.
2.  Navigate to the project root.
3.  Run the application stack:
    ```bash
    docker-compose up --build
    ```
4.  Access the services:
    -   **Frontend:** `http://localhost:3000`
    -   **Backend API:** `http://localhost:8000`
    -   **API Documentation:** `http://localhost:8000/docs` (Swagger UI)

### Running ServicesIndividually

#### Backend
1.  Navigate to the `backend` directory.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Start the server:
    ```bash
    uvicorn app.main:app --reload
    ```

#### Frontend
1.  Navigate to the `frontend` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm run dev
    ```

## Roadmap

-   **Phase 1:** Foundation & Infrastructure Setup (Current - Complete)
-   **Phase 2:** Resume Parsing Engine & Candidate Profile Management (Planned)
-   **Phase 3:** Bias Detection Algorithms & Analysis Pipeline (Planned)
-   **Phase 4:** User Dashboard, Reporting & Visualization (Planned)

---
*Note: This repository contains the source code for Phase 1 of the FairHire-AI project.*
