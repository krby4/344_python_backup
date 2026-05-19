#!/usr/bin/env python3
import os
import csv
import argparse
import logging
import datetime
import pathlib
import shutil
import tarfile
import hashlib
# Python based backup and retention tool
# argument parsing setup
# Supported modes:
# single: back up a single file or directory
# batch: back up multiple paths from a csv file
# verify: verify integrity of backup on its SHA256 checksum
# restore: restore a .bak or .tar.gz archive 
# =================================
# Argument parsing
# =================================
def parse_args():
    # main parser
    parser = argparse.ArgumentParser()
    # subparser for mode
    subparsers = parser.add_subparsers(dest="mode", required=True, help="batch,single,verify,restore")
    # single mode parser 
    single_parser = subparsers.add_parser("single", help="Back up a single directory or file")
    single_input = single_parser.add_mutually_exclusive_group(required=True)
    single_input.add_argument("-f", "--file", help="Path to a single file, will not tar up result",dest="input")
    single_input.add_argument("-p", "--path", help="Path to a single directory, will tar result", dest="input")
    single_parser.add_argument("-o", "--out", help="Output directory for backups and restores, defaults to ./", default="./")
    # batch mode parser
    batch_parser = subparsers.add_parser("batch", help="Back up multiple paths that are read from a csv file")
    batch_input = batch_parser.add_mutually_exclusive_group(required=True)
    batch_input.add_argument("-c", "--csv", help="Path to csv file containing paths to backup targets", dest="input")
    batch_input.add_argument("-g", "--generate", help="Generates a preformatted CSV file with headers to use", action="store_true")
    batch_parser.add_argument("-o", "--out", help="Output directory for backups and restores, defaults to ./", default="./")
    # verify mode parser
    verify_parser = subparsers.add_parser("verify", help="Verify the integrity of a backup")
    verify_parser.add_argument("-a", "--archive", help="Backup file to verify integrity of", required=True)
    # restore mode parser
    restore_parser = subparsers.add_parser("restore", help="Restore files from a backup")
    restore_parser.add_argument("-a", "--archive", help="Archive to restore", required=True)
    restore_parser.add_argument("--overwrite", help="Overwrite files in place, recommended to use after dry-run", action="store_true")
    restore_parser.add_argument("-o", "--out", help="Restore destination, defaults to ./", default="./")
    
    # shared arguments
    for sub in [single_parser, batch_parser, verify_parser, restore_parser]:
        sub.add_argument("--dry-run", action="store_true")
        sub.add_argument("-v", "--verbose", action="store_true")
        sub.add_argument("-l", "--log", nargs="?", const="AUTO", default=None)
    for sub in [single_parser, batch_parser]:
        sub.add_argument("-r", "--retain", type=int, help="Number of old backups to keep")
    
    return parser.parse_args()
# =================================
# Logging
# =================================
def generate_log_name(args):
    # generates log name if you do not specify one in args
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if args.mode == "single":
        name = pathlib.Path(args.input).name
        return name + "_" + date + ".log"
    elif args.mode == "batch":
        if args.generate:
            return "generate_" + date + ".log"
        csv_name = pathlib.Path(args.input).stem
        return "backup_" + csv_name + "_" + date + ".log"
    elif args.mode == "verify":
        archive_name = pathlib.Path(args.archive).stem
        return "verify_" + archive_name + "_" + date + ".log"
    else:
        archive_name = pathlib.Path(args.archive).stem
        return "restore_" + archive_name + "_" + date + ".log"

def make_logfile_name(args):
    # calls generate log name if no log name is given
    if args.log == "AUTO":
        return generate_log_name(args)
    return args.log

def setup_logger(verbose=False, logfile=None):
    # sets up the logger to use for the script including a file handler
    logger = logging.getLogger("backup")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

    level = logging.DEBUG if verbose else logging.INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
        
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
# =================================
# Helpers
# =================================
def make_checksum(in_path, mode="check"):
    # makes a checksum and checksum file using hashlib
    sha256 = hashlib.sha256()

    with open(in_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
        
    checksum = sha256.hexdigest()
    checksum_file = in_path.with_suffix(in_path.suffix + ".sha256")
    if mode == "write":
        with open(checksum_file, "w") as f:
            f.write(f"{checksum}  {in_path.name}\n")
    return checksum 

def make_backup_name(in_path, mode):
    # makes the name of the backup, either a .bak or .tar.gz
    # these names are timestamped to use in retain mode
    # no custom name can be given in args
    date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if mode == "single":
        if in_path.is_file():
            name = in_path.stem
            bak_name = name + "_" + date + ".bak"
        elif in_path.is_dir():
            name = in_path.name
            bak_name = name + "_" + date + ".tar.gz"
        else:
            bak_name = "backup"
    elif mode == "batch":
        csv_name = in_path.stem
        bak_name = csv_name + "_" + date + ".tar.gz"
    return bak_name

def get_backup_class(in_path, mode):
    # defines the postfix for backups
    if mode == "single":
        if in_path.is_file():
            return in_path.stem, ".bak"
        elif in_path.is_dir():
            return in_path.name, ".tar.gz"
    elif mode == "batch":
        return in_path.stem, ".tar.gz"

def make_batch_name(path):
    # used to make paths for the tarfile
    # if its Windows, you need to strip the :
    # if it is linux or mac, you just want to strip the leading / and return as a string
    if os.name == "nt":
        drive = path.drive.rstrip(":")
        tail = path.relative_to(path.anchor)
        if drive:
            return str(pathlib.PurePosixPath(drive) /pathlib.PurePosixPath(tail.as_posix()))
        return str(pathlib.PurePosixPath(tail.as_posix()))
    else:
        tail = path.relative_to(path.anchor)
        return str(pathlib.PurePosixPath(tail.as_posix()))

# =================================
# Mode functions
# =================================
def do_retention(out_dir, prefix, extension, retain_count, logger, dry_run=False):
    # Retention flag logic, used to delete files with same prefix, separated by date
    # Will not work if retain is not flagged or if you specify less than 1
    if retain_count is None:
        return
    
    if retain_count <= 1:
        logger.error("Retain must be bigger than one")
        return
    
    files = []
    # if the item is not a file, does not start with the prefix
    # does not end with .bak or .tar.gz, or does end with .sha256 skip it
    for item in out_dir.iterdir():
        if not item.is_file(): 
            continue
        if item.name.endswith(".sha256"): 
            continue
        if not item.name.startswith(prefix + "_"):
            continue
        if not item.name.endswith(extension):
            continue
        files.append(item)
    # sort them all then make a new list of the first x items
    files.sort(reverse=True)

    if len(files) <= retain_count:
        logger.info("Retention: Nothing to delete")
        return
    
    delete_files = files[retain_count:]
    # if dry run just say you would delete them otherwise use unlink to delete
    for file in delete_files:
        checksum = file.with_suffix(file.suffix + ".sha256")
        
        if dry_run:
            logger.info(f"Dry run: Would delete {file}")
            if checksum.exists():
                logger.info(f"Dry run: Would delete {checksum}")
        else:
            try:
                file.unlink()
                logger.info(f"Deleted {file}")
            except Exception as e:
                logger.error(f"Failed to delete {file}: {e}")
            if checksum.exists():
                try:
                    checksum.unlink()
                    logger.info(f"Deleted {checksum}")
                except Exception as e:
                    logger.error(f"Failed to delete {checksum}: {e}")

def do_single_mode(args, logger):
    # copies with a .bak suffix if a file
    # opens up a tarfile and adds the one directory if directory
    # also makes a directory if your .out doesn't exist
    # generates a checksum to use with verify mode
    in_path = pathlib.Path(args.input)
    bak_name = make_backup_name(in_path, "single")
    out_dir = pathlib.Path(args.out)
    out_path = out_dir / bak_name
    logger.info("Starting single mode")
    if not in_path.exists():
        logger.error("Input path does not exist")
        logger.info("Ending single mode")
        return
    if args.dry_run:
        logger.info(f"Dry run: Would create directory at {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
    # single file mode
    if in_path.is_file():
        if args.dry_run:
            logger.info(f"Dry run: Would copy {in_path} to {out_path}")
            if args.retain:
                prefix, ext = get_backup_class(in_path, "single")
                do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)
        else:
            try:
                shutil.copy2(in_path, out_path)
                make_checksum(out_path,"write")
                logger.info(f"Single file backup successful on {in_path} to {out_path}")
                if args.retain:
                    prefix, ext = get_backup_class(in_path, "single")
                    do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)
            except PermissionError:
                logger.error("Can't write to the out location")
            except Exception as e:
                logger.error(f"Error occurred: {e}")
    # directory mode
    elif in_path.is_dir():
        if args.dry_run:
            logger.info(f"Dry run: Would archive directory {in_path} to {out_path}")
            if args.retain:
                prefix, ext = get_backup_class(in_path, "single")
                do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)
        else:
            try:
                with tarfile.open(out_path, "w:gz") as tar:
                    tar.add(in_path, arcname=in_path.name)
                make_checksum(out_path, "write")
                logger.info(f"Single directory backup successful on {in_path} to {out_path}")
                if args.retain:
                    prefix, ext = get_backup_class(in_path, "single")
                    do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)
            except Exception as e:
                logger.error(f"Error occurred: {e}")
    else:
        logger.error("Input path is not a valid file or directory")

    logger.info("Ending single mode")

def do_batch_mode(args, logger):
    # Creates directory if .out doesn't exist
    # build list of acceptable file paths from csv
    # opens tarfile and adds all paths into the tarfile
    out_dir = pathlib.Path(args.out)
    logger.info("Starting batch mode")

    if args.generate:
        template_path = pathlib.Path(args.out) / "batch_template.csv"

        if args.dry_run:
            logger.info(f"Dry run: Would create CSV template at {template_path}")
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            try:
                with open(template_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["/absolute/path/to/file_or_directory"])
                    writer.writerow(["/another/example/path"])
                logger.info(f"Generated CSV template at {template_path}")
            except Exception as e:
                logger.error(f"Failed to create CSV template: {e}")
        logger.info("Ending batch mode")
        return

    csv_path = pathlib.Path(args.input)
    bak_name = make_backup_name(csv_path, "batch")
    out_path = out_dir / bak_name
    if not csv_path.exists():
        logger.error("CSV input path does not exist")
        logger.info("Ending batch mode")
        return
    
    if not csv_path.is_file():
        logger.error("CSV input wasn't a file")
        logger.info("Ending batch mode")
        return
    
    if csv_path.suffix.lower() != ".csv":
        logger.error("Input file must have a .csv extension")
        logger.info("Ending batch mode")
        return
    if args.dry_run:
        logger.info(f"Dry run: Would create directory at {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    # use csv file to validate the paths
    with open(csv_path) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if not row:
                continue
            raw_path = row[0].strip()
            if not raw_path:
                continue

            path = pathlib.Path(raw_path)
            # only accepts absolute paths
            if not path.is_absolute():
                logger.warning(f"Skipping non-absolute path: {raw_path}")
                continue
            if not path.exists():
                logger.warning(f"Skipping missing path: {raw_path}")
                continue
        
            paths.append(path)
        if not paths:
            logger.error("No valid paths found in CSV input")
            logger.info("Ending batch mode")
            return 

    if args.dry_run:
        logger.info(f"Dry run: would archive {len(paths)} to {out_path}")
        for path in paths:
            arcname = make_batch_name(path)
            logger.info(f"Dry run: Would add {path} as {arcname}")

        if args.retain is not None:
            prefix, ext = get_backup_class(csv_path, "batch")
            do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)

    else:
        try:
            with tarfile.open(out_path, "w:gz") as tar:
                for path in paths:
                    # get absolute path and turn it into a safe relative path
                    arcname = make_batch_name(path)
                    tar.add(path, arcname=arcname)

            make_checksum(out_path, "write")
            logger.info(f"Batch processing successful on {csv_path} to {out_path}")
            if args.retain is not None:
                prefix, ext = get_backup_class(csv_path, "batch")
                do_retention(out_dir, prefix, ext, args.retain, logger, args.dry_run)

        except Exception as e:
            logger.error(f"Error occurred: {e}")

    logger.info("Ending batch mode")

def do_verify_mode(args, logger):
    # takes archive input, runs checksum, and compares it to the existing one
    archive_path = pathlib.Path(args.archive)
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    logger.info("Starting verify mode")

    if not archive_path.exists():
        logger.error("Archive file does not exist")
        logger.info("Ending verify mode")
        return
    
    if not checksum_path.exists():
        logger.error("Checksum file doesn't exist")
        logger.info("Ending verify mode")
        return
    
    try:
        with open(checksum_path, "r") as f:
            line = f.readline().strip()

        if not line:
            logger.error("Checksum file is empty")
            logger.info("Ending verify mode")
            return
        
        expected_checksum = line.split()[0]
        current_checksum = make_checksum(archive_path)

        if current_checksum == expected_checksum:
            logger.info(f"Verification successful for {archive_path}")
        else:
            logger.error(f"Verification failed for {archive_path}")
        
    except Exception as e:
        logger.error(f"Error occurred during verification: {e}")
        
    logger.info("Ending verify mode")

def do_restore_mode(args, logger):
    # Restores the .bak or .tar.gz file
    in_path = pathlib.Path(args.archive)
    out_dir = pathlib.Path(args.out)
    logger.info("Starting restore mode")
    if args.dry_run:
        logger.info(f"Dry run: Would create directory {out_dir}")
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
    if not in_path.exists():
        logger.error("Archive doesn't exist")
        logger.info("Ending restore mode")
        return
    # .bak file, basically just copy and strip the .bak
    if in_path.suffix == ".bak":
        output = out_dir / in_path.stem
        if args.dry_run:
            logger.info(f"Dry run: Would copy {in_path} to {output}")
        else:
            if output.exists() and not args.overwrite:
                logger.warning(f"File exists, skipping: {output}")
            else:
                shutil.copy2(in_path, output)
                logger.info(f"Restored file to {output}")
    # if it is a .tar.gz
    elif in_path.suffixes[-2:] == [".tar", ".gz"]:
        try:
            with tarfile.open(in_path, "r:gz") as tar:
                for member in tar.getmembers():
                    mem_path = out_dir / member.name
                    # prevents path traversal in restore, eg ..
                    if not str(mem_path.resolve()).startswith(str(out_dir.resolve())):
                        logger.warning(f"Unsafe path detected: {member.name}")
                        continue
                    
                    if mem_path.exists() and not args.overwrite:
                        logger.warning(f"Skipping existing file: {member.name}")
                        continue
                    else:
                        if args.dry_run:
                            logger.info(f"Dry run: Would extract {member.name} to {mem_path}")
                        else:
                            tar.extract(member, out_dir)
            if not args.dry_run:
                logger.info(f"Archive restored to {out_dir}")
        except Exception as e:
            logger.error(f"Error restoring archive: {e}")
    else:
        logger.error("Unsupported archive type")
    logger.info("Ending restore mode")

# =================================
# Main
# =================================

def main():
    args = parse_args()
    logfile = make_logfile_name(args)
    logger = setup_logger(args.verbose, logfile)
    if args.mode == "single":
        do_single_mode(args, logger)
    elif args.mode == "batch":
        do_batch_mode(args, logger)
    elif args.mode == "verify":
        do_verify_mode(args, logger)
    elif args.mode == "restore":
        do_restore_mode(args, logger)
    # print(args)

if __name__ == "__main__":
    main()