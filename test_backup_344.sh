#!/usr/bin/env bash
# test my python script by creating files, running the different modes, and generating log files
set -euo pipefail

working_dir=$(pwd)
test_dir="$working_dir/backup_tests"
log_dir="$working_dir/logs"
out_dir="$working_dir/backup_out"
restore_dir="$working_dir/restore"
test_csv="$working_dir/test_csv.csv"

# cleans up previous tests
rm -rf "$test_dir" "$log_dir" "$out_dir" "$restore_dir"
rm -f "$test_csv" "$working_dir/badinput.txt"

# make files to backup and csv for use with batch mode
mkdir -p "$test_dir" "$log_dir" "$out_dir" "$restore_dir"

# helper to get newest matching file
latest_match() {
    find "$1" -maxdepth 1 -type f -name "$2" | sort | tail -n 1
}

(
    cd "$test_dir"
    for i in {1..5}; do
        touch "test_$i.txt"
        echo "test $i" >> "test_$i.txt"
    done
)

# make a csv out of generated files
# python version expects one path per row
{
    echo "$test_dir/test_1.txt"
    echo "$test_dir/test_2.txt"
    echo "$test_dir/test_3.txt"
    echo "     $test_dir/test_4.txt"
    echo "$test_dir/test_5.txt     "
    echo
    echo "relative/path/should/be/skipped"
    echo "$working_dir/does_not_exist.txt"
} > "$test_csv"

# test single file
python3 ./backup_344.py single --file "$test_dir/test_1.txt" -o "$out_dir" --dry-run -v -l "$log_dir/single_file_backup_dry_test1.log"
python3 ./backup_344.py single --file "$test_dir/test_1.txt" -o "$out_dir" -v -l "$log_dir/single_file_backup_test1.log"

single_file_archive=$(latest_match "$out_dir" "test_1_*.bak")

python3 ./backup_344.py verify --archive "$single_file_archive" -v -l "$log_dir/single_file_backup_verify.log"
python3 ./backup_344.py restore --archive "$single_file_archive" -o "$restore_dir" -v -l "$log_dir/single_file_backup_restore.log"

# expected warning (existing file, overwrite off)
python3 ./backup_344.py restore --archive "$single_file_archive" -o "$restore_dir" -v -l "$log_dir/single_file_backup_overwriteoff_restore.log"
python3 ./backup_344.py restore --archive "$single_file_archive" -o "$restore_dir" -v --overwrite -l "$log_dir/single_file_backup_overwriteon_restore.log"

# test single dir
python3 ./backup_344.py single --path "$test_dir" -o "$out_dir" --dry-run -v -l "$log_dir/single_dir_backup_dry_test1.log"
python3 ./backup_344.py single --path "$test_dir" -o "$out_dir" -v -l "$log_dir/single_dir_backup_test1.log"

single_dir_archive=$(latest_match "$out_dir" "backup_tests_*.tar.gz")

python3 ./backup_344.py verify --archive "$single_dir_archive" -v -l "$log_dir/single_dir_backup_verify.log"
python3 ./backup_344.py restore --archive "$single_dir_archive" -o "$restore_dir" -v -l "$log_dir/single_dir_backup_restore.log"

# expected warning (existing files, overwrite off)
python3 ./backup_344.py restore --archive "$single_dir_archive" -o "$restore_dir" -v -l "$log_dir/single_dir_backup_overwriteoff_restore.log"
python3 ./backup_344.py restore --archive "$single_dir_archive" -o "$restore_dir" -v --overwrite -l "$log_dir/single_dir_backup_overwriteon_restore.log"

# test batch
python3 ./backup_344.py batch --generate -o "$out_dir"
python3 ./backup_344.py batch --csv "$test_csv" -o "$out_dir" -v --dry-run -l "$log_dir/batch_backup_dry.log"
python3 ./backup_344.py batch --csv "$test_csv" -o "$out_dir" -v -l "$log_dir/batch_backup.log"

batch_archive=$(latest_match "$out_dir" "test_csv_*.tar.gz")

python3 ./backup_344.py verify --archive "$batch_archive" -v -l "$log_dir/batch_backup_verify.log"
python3 ./backup_344.py restore --archive "$batch_archive" -o "$restore_dir" -v -l "$log_dir/batch_backup_restore.log"

# expected warning (existing files, overwrite off)
python3 ./backup_344.py restore --archive "$batch_archive" -o "$restore_dir" -v -l "$log_dir/batch_backup_overwriteoff_restore.log"
python3 ./backup_344.py restore --archive "$batch_archive" -o "$restore_dir" -v --overwrite -l "$log_dir/batch_backup_overwriteon_restore.log"

# test retain
python3 ./backup_344.py single --file "$test_dir/test_2.txt" -o "$out_dir" -v --retain 2 -l "$log_dir/retain_test1.log"
sleep 1
python3 ./backup_344.py single --file "$test_dir/test_2.txt" -o "$out_dir" -v --retain 2 -l "$log_dir/retain_test2.log"
sleep 1
python3 ./backup_344.py single --file "$test_dir/test_2.txt" -o "$out_dir" -v --retain 2 -l "$log_dir/retain_test3.log"

# help and usage
# expected error
set +e
python3 ./backup_344.py
set -e
python3 ./backup_344.py -h

# some bad input to test, output to badinput.txt in your working dir
set +e
echo "=======================================================================" >> badinput.txt 2>&1
echo "single bad input, cant have --file and --path" > badinput.txt
echo "=======================================================================" >> badinput.txt 2>&1
python3 ./backup_344.py single --file test --path test2 -o test >> badinput.txt 2>&1

echo "=======================================================================" >> badinput.txt 2>&1
echo "batch bad input, no csv file" >> badinput.txt
echo "=======================================================================" >> badinput.txt 2>&1
python3 ./backup_344.py batch -o test3 >> badinput.txt 2>&1

echo "=======================================================================" >> badinput.txt 2>&1
echo "verify bad input, no input archive" >> badinput.txt
echo "=======================================================================" >> badinput.txt 2>&1
python3 ./backup_344.py verify -l >> badinput.txt 2>&1

echo "=======================================================================" >> badinput.txt 2>&1
echo "restore bad input, no archive" >> badinput.txt
echo "=======================================================================" >> badinput.txt 2>&1
python3 ./backup_344.py restore -l >> badinput.txt 2>&1

echo "=======================================================================" >> badinput.txt 2>&1
echo "batch bad input, wrong extension" >> badinput.txt
echo "=======================================================================" >> badinput.txt 2>&1
python3 ./backup_344.py batch --csv "$test_dir/test_1.txt" -o "$out_dir" >> badinput.txt 2>&1
set -e