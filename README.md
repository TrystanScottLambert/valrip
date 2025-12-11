# RIP Validator

This project defines a Python package which validates a directory containing a DIP and its associated metadata to confirm whether or not it is legal as a RIP. Validation includes: 
1. Confirmation that all expected files exist. 
2. Adherence to the WAVES DAML format for dataset-level metadata. 
3. Adherence to the WAVES MAML format for data product-level metadata.
4. Adherence to the WAVES Style Standards. 

# valrip Installation Guide

`valrip` is distributed as precompiled binaries for macOS and Linux.

---

## 1. Determine your architecture

Open a terminal and run:

uname -m

- x86_64 → Intel CPU  
- arm64 → Apple Silicon (macOS) or ARM64 (Linux)

---

## 2. Download the appropriate binary

Use `curl` to download the correct binary. Replace <URL> with the URL of the release binary:

### macOS
# Apple Silicon
curl -L -o valrip <URL-for-macos-arm64>

# Intel
curl -L -o valrip <URL-for-macos-x86_64>

### Linux
# AMD64
curl -L -o valrip <URL-for-linux-amd64>

# ARM64
curl -L -o valrip <URL-for-linux-arm64>

---

## 3. Make it executable and move to your PATH

chmod +x valrip
sudo mv valrip /usr/local/bin/

---

## 4. Verify the installation

valrip --version

---

## 5. Usage

valrip --help
