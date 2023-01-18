import os
import itertools
import compare_mp3

from del_dups_in_dir import mp3_similar


def compare_pairs(files_list, is_similar_func):
    results = {}
    for file1, file2 in itertools.product(files_list, files_list):
        if file1 >= file2:
            continue
        compound_name = file1 + '|' + file2
        results[compound_name] = is_similar_func(file1, file2)
    return results


def create_clusters(files_list):
    last_cluster = 0
    cluster_of_file = {}
    clusters = {}
    for cluster_no, file in enumerate(files_list):
        cluster_of_file[file] = cluster_no
        clusters[cluster_no] = [file]

    for file1, file2 in itertools.product(files_list, files_list):
        if file1 == file2 or cluster_of_file[file1] == cluster_of_file[file2]:
            continue
        if mp3_similar(file1, file2):
            print(f'Similarity: {file1},{file2}')
            if cluster_of_file[file1] > cluster_of_file[file2]:
                file2, file1 = file1, file2
            # Now file1 belongs to cluster with lower number
            cluster_to_merge = cluster_of_file[file2]
            print(
                f'Merging {file2} cluster {cluster_to_merge} containing {clusters[cluster_to_merge]} into cluster {cluster_of_file[file1]} containing {clusters[file1]}')
            cluster_of_file[file2] = cluster_of_file[file1]
            clusters[file1].extend(clusters[cluster_to_merge])
            clusters[cluster_to_merge] = None
    print("Final clusters:")
    for cluster_no, c_files in clusters.items():
        print(f'Cluster {cluster_no} contains file:')
        print('\n'.join(c_files))
        print('-----')


if __name__ == "__main__":
    dir = "E:\\mp3_similarity_test\\"  # "R:\\mp3\\שחר סגל ורועי בר נתן\\גלי צה_ל\\"
    files = [dir + file for file in os.listdir(dir)]
    files = [file for file in files if os.path.isfile(file)]
    results = compare_pairs(files, mp3_similar)
    print(results)

    dbfile = ''
    db = TinyDB(dbfile)
    # create_clusters(files)
