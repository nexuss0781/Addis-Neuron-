# Project: Agile Mind - A Logical AGI

This repository contains the source code for "Agile Mind," a new type of artificial general intelligence built from first principles. Unlike traditional LLMs, this project focuses on building a brain that learns through logical structuring of information, not statistical pattern recognition.

## Architecture

The system is architected as a set of containerized microservices, primarily using Python for high-level orchestration and Rust for performance-critical logical engines.

-   **/python_app:** The main control layer, handling I/O and managing the learning process.
-   **/rust_engine:** The core logical processing units, including the LVE and HSM.
-   **/docker-compose.yml:** The orchestration file to launch the entire brain's infrastructure.

## Getting Started

1.  Ensure Docker and Docker Compose are installed.
2.  Clone the repository.
3.  From the root directory, run `docker-compose up --build`.
