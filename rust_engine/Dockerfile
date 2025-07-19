# --- Stage 1: The Builder ---
# Use the official Rust image as the build environment
FROM rust:1-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# Create a new, empty cargo project. This is a trick to cache dependencies.
# This way, Docker only re-compiles dependencies if Cargo.toml changes.
RUN USER=root cargo new --bin logical_engine
WORKDIR /usr/src/app/logical_engine

# Copy the dependency manifest
COPY logical_engine/Cargo.toml ./
COPY logical_engine/Cargo.lock ./

# Build a blank project to cache dependencies
RUN cargo build --release
RUN rm src/*.rs target/release/deps/logical_engine*

# Now, copy the actual source code and build it
COPY logical_engine/src ./src
RUN cargo build --release

# --- Stage 2: The Final Image ---
# Use a minimal base image for the final container
FROM debian:bullseye-slim

# Set up a non-root user for security
RUN groupadd -r rust_user && useradd -r -g rust_user rust_user

# Copy the compiled binary from the builder stage
COPY --from=builder /usr/src/app/logical_engine/target/release/logical_engine /usr/local/bin/

# Set the non-root user as the default user
USER rust_user

# Expose the port the app runs on
EXPOSE 8000

# Set the command to run our compiled application
CMD ["/usr/local/bin/logical_engine"]
