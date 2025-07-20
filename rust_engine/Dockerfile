# --- Stage 1: The Builder ---
# This stage compiles our code in release mode for production.
FROM rust:1-slim as builder

WORKDIR /usr/src/app

# We need a minimal project structure for cargo to work
RUN mkdir -p src && echo "fn main() {}" > src/main.rs

# Copy dependency manifests
COPY Cargo.toml Cargo.lock* ./

# Fetch and build dependencies separately to leverage Docker layer caching
RUN cargo fetch
RUN cargo build --release
RUN rm -f target/release/deps/logical_engine*

# Copy the actual source code and build the final binary
COPY src ./src
RUN cargo build --release

# --- Stage 2: The Final Image for Development & Testing ---
# This stage uses the same base to ensure compatibility and includes source code
FROM rust:1-slim

# Install any build tools that might be needed by dependencies during `cargo test`
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Set the working directory (where our mounted volume will be)
WORKDIR /usr/src/app

# Set up a non-root user for security
RUN useradd -ms /bin/bash rust_user
USER rust_user

# Copy the pre-compiled binary from the builder stage.
# When we run the container, it will use this fast, pre-compiled version.
# When we mount our local code, we can re-compile inside the container for testing.
COPY --from=builder /usr/src/app/target/release/logical_engine /usr/local/bin/

# Expose the port the app runs on
EXPOSE 8000

# Set the default command to run our pre-compiled application
CMD ["/usr/local/bin/logical_engine"]

