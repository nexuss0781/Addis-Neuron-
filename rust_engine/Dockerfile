# --- Stage 1: The Builder ---
# Use the official Rust image as the build environment
FROM rust:1-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# We need a minimal project structure for cargo to work
# Create dummy main.rs before fetching dependencies
RUN mkdir -p src
RUN echo "fn main() {}" > src/main.rs

# Copy dependency manifests
COPY Cargo.toml Cargo.lock* ./

# Fetch dependencies based on lock file.
# This is now guaranteed to work because src/main.rs exists.
RUN cargo fetch
RUN cargo build --release
RUN rm -f target/release/deps/logical_engine*

# Now, copy the actual source code and build it, overwriting the dummy
COPY src ./src
RUN cargo build --release

# --- Stage 2: The Final Image ---
# Use the SAME base image as the builder to ensure glibc compatibility.
FROM rust:1-slim

# Set up a non-root user for security
RUN useradd -ms /bin/bash rust_user

# Copy the compiled binary from the builder stage
COPY --from=builder /usr/src/app/target/release/logical_engine /usr/local/bin/

# Set the non-root user as the default user
USER rust_user

# Expose the port the app runs on
EXPOSE 8000

# Set the command to run our compiled application
CMD ["/usr/local/bin/logical_engine"]
