import os
import shutil
import zipfile


def extract_zipfile(dirpath, name):
    zipfile_path = os.path.join(dirpath, name + '.zip')

    extracted_path = os.path.join(dirpath, name)
    if zipfile.is_zipfile(zipfile_path) and not os.path.isdir(extracted_path):
        print('Extracting: ' + name)
        zf = zipfile.ZipFile(zipfile_path)
        zf.extractall(dirpath)
    return extracted_path


def ensure_directory(base_dir, sub_dir):
    dir = os.path.join(base_dir, sub_dir)
    try:
        os.mkdir(dir)
    except:
        pass
    return dir


def copy_files(fname_pattern, start, number, src_root, dest_root):
    fnames = [fname_pattern.format(i) for i in range(start, start + number)]
    for fname in fnames:
        src = os.path.join(src_root, fname)
        dest = os.path.join(dest_root, fname)
        shutil.copyfile(src, dest)


def listdir(path, recursive=False):
    if not recursive:
        return os.listdir(path)
    files = []
    for root, directories, filenames in os.walk(path):
        files += filenames
    return files
