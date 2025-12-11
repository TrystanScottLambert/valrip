# RIP Validator

This project defines a Python package which validates a directory containing a DIP and its associated metadata to confirm whether or not it is legal as a RIP. Validation includes: 
1. Adherence to the WAVES MAML format for data product-level metadata.
2. Adherence to the WAVES Style Standards. 

# valrip Installation Guide

`valrip` is distributed as precompiled binaries for macOS and Linux.

---

## 1. Determine your architecture

Open a terminal and run:

```
uname -m
```

- x86_64 → Intel CPU  
- arm64 → Apple Silicon (macOS) or ARM64 (Linux)

---

## 2. Download the appropriate binary

Use `curl` to download the correct binary. Replace <URL> with the URL of the release binary:

### macOS
# Apple Silicon
```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-macos-arm64
```

# Intel
```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-macos-x86_64
```

### Linux
# AMD64
```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-linux-amd64
```

# ARM64
```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-linux-arm64
```

---

## 3. Make it executable and move to your PATH

```
chmod +x valrip && sudo mv valrip /usr/local/bin/
```

---

## 4. Verify the installation

```
valrip --help
```

## Troubleshooting
### Macos

**Problem:** Running the app results in a popup that states something to the effect of:  

_"valrip" Not Opened_  
_Apple could not verify "valrip" is free of malware that may harm your Mac or compromise your privacy._

**Solution:** Go to Settings > Privacy & Security > Open Anyway (under Settings | valrip). This will allow your Mac to open the app. 

