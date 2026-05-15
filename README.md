# RIP Validator

This project defines a Python package which validates a directory containing a DIP and its associated metadata to confirm whether or not it is legal as a RIP.

# Usage
`valrip` is a CLI tool - it is run via a command line interface. 
See the installation instructions below. 

Open a terminal in any app and run `valrip --help` to see the options. 
## valrip parquet
Valrip can be used to validate an individual Parquet file to check its adherence to the WAVES Style Standards. To validate your Parquet file, run `valrip parquet <path_to_parquet_file>`, e.g.: `valrip parquet /Home/group_catalogue/group_catalogue.parquet`. There will be output describing whether the Parquet file is valid, or invalid. If it is invalid, a list of the errors will be displayed for you to correct. Please note that only the errors are required to be corrected, warnings are suggestions only. 

## valrip maml
Another option is to validate an individual MAML file to check its adherence to MAML and WAVES-MAML. To validate your MAML file, run: `valrip maml <path_to_maml_file>`, e.g.: `valrip maml /Home/group_catalogue/group_catalogue.maml`. There will be output describing whether the MAML file is valid, or invalid. If it is invalid, a list of the errors will be displayed for you to correct. Please note that only the errors are required to be corrected, warnings are suggestions only.  

## valrip consistent
Even though the parquet file and maml file have been validated, it is important to make sure that they are consistent with one another. I.e., that the maml file accurately represents the parquet file. This can be done with `valrip consistent`. For example, for data called `groups.parquet` with a corresponding maml file `groups.maml`, the consistency of both can be checked with `valrip consistent groups` (Note that there is no need to add the file extension here since .maml and .parquet will be assumed). 

## valrip directory
Once all tables and their metadata have been validated to be consistent the entire rip-level needs to validated to check for extra or missing files, inconsistent naming of datasets throughought the tables, and populate the data-set level metadata. Run `valrip directory <path/to/directory>` to validate the entire directory. Once this has passed validation the entire folder can be uploaded to the QC folder in the WAVES DC owncloud.

## valrip submit
Once all the files have been uploaded to the right folder, say "group_nessie", then you can submit that folder to QC very simply with `valrip submit group_nessie`. 

## valrip gen-maml
A helper method exists in `valrip` to generate a skeletal maml structure for a given parquet file that populates the fields columns which can be quite coumbersome. `valrip gen-maml groups.parquet`.

## valrip login
Some of the functionality requires you to login to the WAVES GitLab and the owncloud space. `valrip login` will allow prompt you for you usernames for these services and store them on your own machine. These credentials will then be used during the submission process. You can also login to either the GitLab or owncloud separately: 
```
valrip login gitlab
valrip login owncloud
```

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

Download the correct binary using `curl`:

### macOS
#### Apple Silicon (arm64)
These are usually newer Macs.

```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v2.1.0/valrip-macos-arm64
```

#### Apple Intel (x86_64)
These are usually older Macs.

```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v2.1.0/valrip-macos-x86_64
```

### Linux
#### AMD64 (x86_64)
This is the most common supported archetecture for linux.
```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v2.1.0/valrip-linux-amd64
```

#### Linux (arm64)
More exotic linux distros may require the arm64 build.

```
curl -L -o valrip https://github.com/TrystanScottLambert/valrip/releases/download/v2.1.0/valrip-linux-arm64
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
