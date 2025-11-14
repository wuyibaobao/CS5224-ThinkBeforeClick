# 🛡️ ThinkBeforeClick - Phishing Simulation & Security Awareness Platform

**Project: CS5224 Cloud Computing (AY25/26 Semester 1) - Group Project**
**Group Nickname: ThinkBeforeClick**

---

## 1. 💡 Project Overview (SaaS Theme)

ThinkBeforeClick is an interactive and adaptive fraud and phishing training SaaS platform built on a 100% AWS Serverless architecture.

This project is designed to tackle the growing risk of phishing and online scams, which are leading causes of financial loss and security breaches globally. We provide **Individual Users** with free, interactive modules to enhance their security awareness, and an **Enterprise Platform** for organizations to launch customized phishing simulations, track employee responses, and receive quantifiable analytics to reduce their security exposure.

## 2. 🚀 Core Features

* **Dual User System**: Differentiates between Individual and Enterprise users with distinct features.
* **Enterprise Registration**: Supports enterprise admins registering with a unique "Company ID" (`custom:admin_username`).
* **Admin Dashboard**:
    * Real-time analytics (Emails Sent, Open Rate, Click Rate).
    * Employee management (Add, View).
    * One-click phishing simulation deployment.
* **Realistic Simulations**:
    * Includes 10+ phishing templates based on real-world, localized scenarios (e.g., DBS Bank, SingPost, NUS).
    * Links lead to high-fidelity, pixel-perfect fake landing pages.
* **Teachable Moment**:
    * After an employee "falls" for a scam, they are immediately redirected to a "WARNING!" page.
    * This page explains the "Red Flags" they missed (e.g., sense of urgency, generic greeting).
* **Dynamic Analytics Report**:
    * Auto-generates a detailed report with template performance, employee vulnerability rankings, and scam-type analysis.
    * Supports printing to PDF for compliance and auditing.

## 3. 📸 Screenshots

**(Please embed your project screenshots here. You can create a `docs/` folder in your repo, upload the images, and link them.)**

| Admin Dashboard | Phishing Email (DBS Template) |
| :---: | :---: |
| <img src="docs/image_e7f1e3.jpg" width="400"> | <img src="docs/image_e878ec.jpg" width="400"> |
| **"Teachable Moment" Page** | **Final Analytics Report** |
| <img src="docs/image_e87962.jpg" width="400"> | <img src="docs/image_e8de21.jpg" width="400"> |

---

## 4. 🛠️ Architecture & Tech Stack

This project is built on a 100% AWS Serverless architecture, ensuring high availability, automatic scaling, and minimal operational overhead.

### Architecture Diagram
(Embed your architecture diagram image here from your `ThinkBeforeClick-Preliminary-1.pdf`)

### Tech Stack
* **Frontend**: HTML5, CSS (TailwindCSS), JavaScript
* **Frontend Hosting**: **AWS S3** (For storing static website files)
* **CDN**: **AWS CloudFront** (For global content delivery and caching)
* **Identity**: **Amazon Cognito** (Manages all user registration, login, and user pools)
* **Backend API**: **Amazon API Gateway** (Provides RESTful API endpoints)
* **Backend Logic**: **AWS Lambda** (Runs all business logic using Python 3.9)
* **Database**: **Amazon DynamoDB** (NoSQL database for all business data)
* **Email Service**: **Amazon SES** (For sending simulation emails)
* **Logging & Monitoring**: **Amazon CloudWatch** (Collects all logs from Lambda and API Gateway)

---

## 5. 🗺️ Core Logic Map

This section maps our core features directly to the backend Lambda functions and database tables that power them.

| Feature | Corresponding Lambda (File) | Database Table(s) |
| :--- | :--- | :--- |
| **User Registration (Enterprise & Individual)** | `lambda/register.py` | `ThinkBeforeClick-Users`, `ThinkBeforeClick-Companies` |
| **User Login** | `lambda/login.py` | (N/A - Handled by Cognito) |
| **Add New Employee** | `lambda/add_employee.py` | `ThinkBeforeClick-Users` (or `Employees`) |
| **Get Employee List** | `lambda/get_employees.py` | `ThinkBeforeClick-Users` (or `Employees`) |
| **Send Phishing Email** | `lambda/send_phishing_email.py` | `EmailTracking` |
| **Track Email Open** | `lambda/track_email_open.py` | `EmailTracking` |
| **Track Scam Click** | `lambda/track_scam_click.py` | `ScamClicks` |
| **Generate Company Report** | `lambda/generate_company_report.py` | `EmailTracking`, `ScamClicks`, `ThinkBeforeClick-Users` |

---

## 6. 📁 Codebase Structure
