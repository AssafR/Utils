import shutil
import itertools
from pathlib import Path
import os
import re
import random

import compare_mp3
from filehash import FileHash
import click
from tinydb import TinyDB, Query
from compare_mp3 import compare


@click.command()
@click.option('--dirname', required=True, type=str)
@click.option('--dbfile', required=False, type=str, default="dupfiles.json", show_default=True)
@click.option('--bruteforce', is_flag=True)
def finddups(**kwargs):
    dirname = kwargs['dirname']
    brute = kwargs['bruteforce']
    dirpath = Path(dirname)
    dbfile = kwargs['dbfile']
    print(f"Working on directory: {dirname}")
    print(f"Working using DB: {dbfile}")
    db = get_db_files(dbfile, dirname, dirpath)
    print(f"Total {len(db)} files")
    files_hash_dict = store_files_as_list_by_hash(db)
    print(f'Number of unique hashes: {len(files_hash_dict.keys())}')
    deletions = delete_all_but_one_copy(files_hash_dict)
    all_deleted_files = list(
        itertools.chain.from_iterable([to_delete for key, (to_delete, to_save) in deletions.items()]))
    all_surviving_files = [to_save for key, (to_delete, to_save) in deletions.items()]

    print(f'Total deleted files:{len(all_deleted_files)}, surviving files: {len(all_surviving_files)}')
    target_to_delete = dirpath / 'delete'
    os.makedirs(str(target_to_delete), exist_ok=True)
    for filename in all_deleted_files:
        full_filename = str(dirpath / filename)
        if os.path.isfile(full_filename):
            shutil.move(full_filename, str(target_to_delete / filename))
            pass


def delete_all_but_one_copy(files_hash_dict):
    deletions = {}
    for file_hash, file_list in files_hash_dict.items():
        print(f'Hash: {file_hash}, Files:{len(file_list)}')
        files_to_delete = battle_between_duplicate(file_list)
        surviving_file = set(file_list) - set(files_to_delete)
        deletions[file_hash] = (files_to_delete, surviving_file)
        print(f'Files: {file_list}')
        print(f'Deleting: {files_to_delete}')
        print('-------')
    return deletions


def store_files_as_list_by_hash(db):
    files_hash_dict = {}
    for item in db:
        current_hash = item['Hash']
        if current_hash not in files_hash_dict:
            files_hash_dict[current_hash] = []
        files_hash_dict[current_hash].append(item['File'])
    return files_hash_dict


def battle_between_duplicate(dup_list):
    lst = dup_list.copy()
    to_delete_lst = []
    while len(lst) > 1:
        name1, name2 = random.sample(lst, k=2)
        print(f'Battling: {name1} <> {name2}')
        to_delete = choose_which_to_delete(name1, name2)
        # print(f' Chose to delete: {to_delete}')
        lst.remove(to_delete)
        to_delete_lst.append(to_delete)
    print(f'Final winner: {lst[0]}')
    print('---')
    return to_delete_lst


def mp3_similar(file1, file2):
    try:
        diff = compare_mp3.compare(file1, file2)
        return not diff == compare_mp3.Result.DIFFERENT
    except:
        return False


def create_clusters(files_list):
    last_cluster = 0
    cluster_of_file = {}
    clusters = {}
    for cluster_no, file in enumerate(files_list):
        cluster_of_file[file] = cluster_no
        clusters[cluster_no] = [file]

    for file1, file2 in itertools.product(cluster_of_file):
        if file1 == file2:
            continue
        if mp3_similar(file1, file2):
            print(f'Similarity: {file1},{file2}')
            if cluster_of_file[file1] > cluster_of_file[file2]:
                file2, file1 = file1, file2
            # Now file1 belongs to cluster with lower number
            cluster_to_merge = cluster_of_file[file2]
            print(f'Merging {file2} cluster {cluster_to_merge} containing {clusters[cluster_to_merge]} into cluster {cluster_of_file[file1]} containing {cluster[file1]}')
            cluster_of_file[file2] = cluster_of_file[file1]
            clusters[file1].extend(clusters[cluster_to_merge])
            clusters[cluster_to_merge] = None


def find_numbers_in_parentheses(name: str):
    numbers = [int(s.replace('(', '').replace(')', '')) for s in re.findall(r'\(\d+\)', name)]
    return numbers


def no_hebrew(str):
    re_hebrew = '[א-ת]'
    hebs = re.findall(re_hebrew, str)
    return len(hebs) == 0;


def choose_which_to_delete(filename1, filename2):
    if no_hebrew(filename1) and not no_hebrew(filename2):
        return filename1
    if no_hebrew(filename2) and not no_hebrew(filename1):
        return filename1
    if 'copy' in filename1.lower():
        return filename1;
    if 'copy' in filename2.lower():
        return filename2;
    numbers1 = find_numbers_in_parentheses(filename1)
    numbers2 = find_numbers_in_parentheses(filename2)
    if len(numbers1) < len(numbers2):
        return filename2
    if len(numbers2) < len(numbers1):
        return filename1
    for n in range(0, len(numbers1)):
        if numbers1[n] < numbers2[n]:
            return filename2
        if numbers2[n] < numbers1[n]:
            return filename1
    return filename1


def get_db_files(dbfile, dirname, dirpath):
    db = TinyDB(dbfile)
    md5hasher = FileHash('md5')
    MyFile = Query()
    for file in []:  # os.listdir(str(dirpath)):
        full_name = str(dirpath / file)
        if not os.path.isfile(full_name):
            continue
        if len(db.search(MyFile.File == file)) == 0:
            file_hash = md5hasher.hash_file(full_name)
            print(f'Hash: {file_hash}, file:[{file}]')
            Item = {'Dir': dirname, 'Hash': file_hash, 'File': file}
            db.insert(Item)
    return db


#
# cli.add_command(filename)
# cli.add_command(finddups)

if __name__ == "__main__":
    finddups()
