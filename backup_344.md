Python based backup and retention tool
argument parsing setup
Supported modes:
single: back up a single file or directory
batch: back up multiple paths from a csv file
verify: verify integrity of backup on its SHA256 checksum
restore: restore a .bak or .tar.gz archive 

Example usage:
Single:
./backup_344.py single -p /path/to/directory -o ./backupsrestore_dir
./backup_344.py single -f /path/to/file.txt -o ./backups --retain 5
Batch
./backup_344.py batch -c ./targets.csv -o ./backups --retain 3
Generate
./backup_344.py batch -g -o ./backups/templates/
Verify
./backup_344.py verify -a ./backups/file_2026-04-15_20-10-22.bak
Restore
./backup_344.py restore -a ./backups/file_2026-04-15_20-10-22.bak -o ./restore_dir -l

## Refactor, Enhancements and New Features
### 1. Refactor
The original project used case switches for option parsing, global variables and a few very small functions that really only existed to satify the function number requirements. I refactored to improve maintainability by:
- replacing manyual switch arg parsing with argparse and subcommands. The bash script had 4 different functions to parse arguments, this script uses argparse and one function with mutually exclusinve argument groups
- moved a lot of mode specify logic into dedicated helper functions. Main() still had quite a bit of mode specific execution in the bash script. In the python one, it is pretty much just do_single_mode(args,logger)
- replaced shell path and text manipulation with python in regards to all paths passed in with the csv and the tarfile generation for batch mode. Modules used were pathlib and csv
- pathlib allowed better and safer path manipulation and validation
- tarfile generation is now a lot safer, able to skip paths that error out individually
- reduced bash specific shell tools with shutil.copy, tarfile, hashlib, and csv 

### 2. Enhancements
**Improved Logging:**
This script uses the standard logging module to provide cleaner logs, optional log file creation, and verbose output support

**Improved argument parsing**
I used argparse to create the argument parsing and help. This makes command usage more clear, adds better variables for use, and removed the need to manually parse the logic

**Expanded dry-run support:**
The dry-run support has been expanded to more consistently apply, with more things logged

### 3. New features
**Retention Support**
Added the feature to be able to specify a number of backups to maintain after running.

**Multi-OS support**
By using pathlib and safer archive path handling, I was able to add Windows compatibility as well as improve linux and mac handling

## Testing Methods

This project is fully testable on a local machine. A Bash test script was used to validate:

- argument parsing
- dry-run behavior
- logfile creation
- single file backups
- single directory backups
- checksum generation
- checksum verification
- tamper detection
- retention behavior
- batch mode with valid and invalid CSV rows
- restore behavior with and without overwrite
- There is a testing script for bash in the submitted project that runs through all of the same things as my bash testing script, it just has a helper function to find the latest created file because i auto generate the file names now