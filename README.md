# RIP Validator

This project defines a Python package which validates a directory containing a DIP and its associated metadata to confirm whether or not it is legal as a RIP. Validation includes: 
1. Adherence to the WAVES MAML format for data product-level metadata.
2. Adherence to the WAVES Style Standards. 

# Usage
`valrip` is a CLI tool - it is run via a command line interface. 

1. See the installation instructions below. 
2. Open a terminal in any app (`terminal`, `VScode`, `RStudio`, etc.) and run `valrip --help` to see the options. 
3. **Validate Parquet**: 
One option is to validate an individual Parquet file to check its adherence to the WAVES Style Standards.To validate your Parquet file, run `valrip parquet <path_to_parquet_file>`, e.g.: `valrip maml /Home/group_catalogue/group_catalogue.parquet`. There will be output describing whether the Parquet file is valid, or invalid. If it is invalid, a list of the errors will be displayed for you to correct. Please note that only the errors are required to be corrected, warnings are suggestions only.  
**Validate MAML**:  
Another option is to validate an individual MAML file to check its adherence to MAML and WAVES-MAML. To validate your MAML file, run: `valrip maml <path_to_maml_file>`, e.g.: `valrip maml /Home/group_catalogue/group_catalogue.maml`. There will be output describing whether the MAML file is valid, or invalid. If it is invalid, a list of the errors will be displayed for you to correct. Please note that only the errors are required to be corrected, warnings are suggestions only.  
**Validate Parquet and MAML together** (validating each and ensuring their consistency):  
The last option is to validate your Parquet and MAML files together. This will perform the individual validation (confirming each files adherence to the WAVES standards) and validation that the two are consistent. To validate your Parquet and MAML file, run `valrip <path_to_maml_and_parquet_files>`, e.g.: `valrip both /Home/group_catalogue/group_catalogue`. There will be output describing whether the files are valid, or invalid. If at least one is invalid, or they are inconsistent, a list of the errors will be displayed for you to correct. Please note that only the errors are required to be corrected, warnings are suggestions only. 

# Installation

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

Use `curl` to download the correct binary using `curl`:

### macOS
#### Apple Silicon (arm64)
These are usually newer Macs.

```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-macos-arm64
```

#### Apple Intel (x86_64)
These are usually older Macs.

```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-macos-x86_64
```

### Linux
#### AMD64 (x86_64)
This is the most common supported archetecture for linux.
```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-linux-amd64
```

#### Linux (arm64)
More exotic linux distros may require the arm64 build.

```
curl -L -o valrip https://github.com/TrystanScottLambert/testing_deployment/releases/download/v0.0.5/valrip-linux-arm64
```

---

## 3. Add valrip to your binary file
To finish the installation simply make the binary executable and then move into your `/usr/local/home/` directory. You will be prompted for your system password. Run: 

```
chmod +x valrip
sudo mv valrip /usr/local/bin/
```

---

## 4. Verify the installation

`valrip --help`


## Troubleshooting

**Problem (macos)**: Running the app results in a popup that states something to the effect of: 
> "valrip" Not Opened  
> Apple could not verify "valrip" is free of malware that may harm your Mac or compromise your privacy. 

**Solution**: Go to Settings > Privacy & Security > Open Anyway (under Settings | valrip). This will allow your Mac to open the app. 