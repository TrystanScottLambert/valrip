# RIP Validator

This project defines a Python package which validates a directory containing a DIP and its associated metadata to confirm whether or not it is legal as a RIP. Validation includes: 
1. Confirmation that all expected files exist. 
2. Adherence to the WAVES DAML format for dataset-level metadata. 
3. Adherence to the WAVES MAML format for data product-level metadata.
4. Adherence to the WAVES Style Standards. 



# Usage
Dior please write this :'(


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
Depending on your archetecture and operating system you will have to download the appropriate binary using `curl`
### Apple Silicon chips (arm64)
These are usually newer Macs.
```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v0.0.5/valrip-macos-arm64

```

### Apple Intel (x86_64)
These are usually older Macs.
```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v0.0.5/valrip-macos-x86_64
```

### Linux (x86_64)
This is the most common supported archetecture for linux.
```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v0.0.5/valrip-linux-amd64
```

### Linux (arm64)
More exotic linux distros may require the arm64 build.
```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v0.0.5/valrip-linux-arm64
```

## 3. Add valrip to your binary file
To finish the installation simply make the binary executable and then move into your `/usr/local/home/` directory. You will be prompted for your system password.

```
chmod +x valrip
sudo mv valrip /usr/local/bin/
```

## 4. Verify install is correct.
`valrip` should now be installed. You can verify this with the --help or --version flags.

```
valrip --help
```

If that works without errors then the install is correct.

### Simon Driver
If your name is Prof. Simon Driver, you can copy and paste the code snippet below and put it in your terminal.

```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v0.0.5/valrip-macos-x86_64
chmod +x valrip
sudo mv valrip /usr/local/bin/
```
