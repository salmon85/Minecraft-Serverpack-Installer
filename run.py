import os
from os.path import join
from os import listdir
import subprocess
from time import sleep
import glob
from shutil import move, rmtree, copy
from get_modpack_info import get_server_modpack_url, get_modpack_minecraft_version
from get_forge_or_fabric_version import get_forge_or_fabric_version_from_manifest
from download_file import download
from ptero_api_func import update_new_forge
from unzip_modpack import unzip
from serverstarter_func import change_installpath
from ptero_api_func import get_server_id
import psutil
import pathlib
import platform
import sys
import oschmod

mode = sys.argv[1] # currently only accepts mode "normal", and "pterodactyl" (without quotations). pterodactyl mode will move the files to the root directory of the install script at the end.
modpack_id = sys.argv[2] # Curseforge modpack ID.
modpack_version = sys.argv[3] # Modpack version to guess. Feature isn't perfect yet. Put "latest" for latest (without quotations).
clean_startup_script = sys.argv[4] # If to clean (remove) the provided startup scripts (.sh for linux and .bat for Windows) when installing the server modpack. Set to "True" or "False".

if mode == "pterodactyl":
    server_uuid = sys.argv[5] # Used to get the UUID of the currently installing server.
    panel_url = sys.argv[6]
    application_api_key = sys.argv[7]

minecraft_version = str(get_modpack_minecraft_version(modpack_id))

print("Installer running in", mode, "mode.")
print("Received arguments to download modpack with ID", modpack_id, "with version", modpack_version, "using minecraft version", minecraft_version)

#Checks OS to know which install file to execute (.bat or .sh)
operating_system = platform.system()

this_dir = os.path.dirname(os.path.realpath(__file__))

def up_one_directory(root, parent):
    for filename in os.listdir(join(root, parent)):
        try:
            if os.path.isfile(join(root, filename)):
                os.remove(join(root, filename))
                print("Replaced Already Existing File:", filename)
            if os.path.isdir(join(root, filename)):
                delete_tree_directory(join(root, filename))
                print("Replaced Already Existing Folder:", filename)
        except:
            pass
        move(join(root, parent, filename), join(root, filename))
    sleep(2)

def delete_directory(dir):
    os.rmdir(dir)
    print("Deleted directory in:", dir)

def delete_tree_directory(dir):
    rmtree(dir)
    print("Deleted tree directory in:", dir)

def kill(proc_pid):
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()
    sleep(3)

# -EXAMPLE MODPACK PROJECT (Addon) IDs on CurseForge-
# SevTech_Ages_of_the_Sky = 403521
# All_the_Mods_6 = 381671
# SkyFactory_4 = 296062
# Roguelike_Adventures_And_Dungeons = 289267
# #The_Pixelmon_Modpack = 389615 #Technic Serverpack
# MC_Eternal = 349129
# Enigmatica_6 = 389471
# Dungeons_Dragons_And_Space_Shuttles = 301717
# Life_In_The_Village_2 = 402412
# Zombie_Apocalypse = 445369
# Better_Minecraft_Forge = 429793
# Better_Minecraft_Fabric = 452013
# #FTB_Revelation = 283861 #FTB Serverpack

modpack_info = get_server_modpack_url(modpack_id, modpack_version)
modpack_name = modpack_info[0]
modpack_urls = modpack_info[1]
modpack_normal_downloadurl = modpack_info[2]



#Grab URLs to modpack and download
if (modpack_urls["SpecifiedVersion"]):
    print("Downloading Specified Version of", modpack_name + "...")
    filename = download(modpack_urls["SpecifiedVersion"])

elif (modpack_urls["LatestReleaseServerpack"]):
    print("Downloading Latest Release of", modpack_name + "...")
    filename = download(modpack_urls["LatestReleaseServerpack"])

elif not modpack_urls["LatestReleaseServerpack"] and modpack_urls["LatestBetaServerpack"]:
    print("Downloading Latest Beta of", modpack_name + "...")
    filename = download(modpack_urls["LatestBetaServerpack"])

elif not modpack_urls["LatestReleaseServerpack"] and not modpack_urls["LatestBetaServerpack"] and modpack_urls["LatestAlphaServerpack"]:
    print("Downloading Latest Alpha of", modpack_name + "...")
    filename = download(modpack_urls["LatestAlphaServerpack"])

elif not modpack_urls["LatestReleaseServerpack"] and not modpack_urls["LatestBetaServerpack"] and not modpack_urls["LatestAlphaServerpack"] and modpack_urls["LatestReleaseNonServerpack"]:
    print("Downloading Latest Non-Serverpack of", modpack_name + "...")
    filename = download(modpack_urls["LatestReleaseNonServerpack"])

sleep(2)

#Unzip downloaded modpack zip
print("Extracting downloaded modpack archive...")
folder_name = unzip(filename, modpack_name)


modpack_folder = os.listdir(join(this_dir, folder_name))

#Count number of files
file_count = 0
for modpack_file in modpack_folder: 
    file_count += 1

#print(filename[:-8].replace("+", " "))


#Move subdirectory to main directory if zip file is double-foldered
existing_subdir = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*"):
    if os.path.isdir(name):
        folder_list = listdir(name)
        for file in folder_list:
            #print(file)
            if (file.endswith(".sh") or file.endswith(".bat") or file == "mods") and file != "kubejs":
                existing_subdir = True
                existing_subdir_path = name

if existing_subdir:
    print("Found nested folder, moving contents to parent directory...")
    #print(this_dir + "/" + folder_name + "/" + folder_name)
    subfolder_path = pathlib.PurePath(existing_subdir_path)
    subfolder_name = subfolder_path.name
    up_one_directory(this_dir + "/" + folder_name, this_dir + "/" + folder_name + "/" + subfolder_name)
    sleep(2)
    delete_directory(this_dir + "/" + folder_name + "/" + subfolder_name)

# Deletes existing libraries and user jvm args file (required for forge 1.17+)
for libraries in glob.glob(glob.escape(this_dir + "/" + folder_name + "/" ) + "libraries"):
    print("Found and deleting old libraries folder", libraries, ". Deleting")
    delete_tree_directory(libraries)
for user_jvm_args in glob.glob(glob.escape(this_dir + "/" + folder_name + "/" ) + "user_jvm_args.txt"):
    print("Found and deleting old user_jvm_args", user_jvm_args)
    os.remove(user_jvm_args)

#Check if forge installer exists in serverpack dir. If does, run it.
forge_installer = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*forge*installer*.jar"):
    if name:
        forge_installer = True
        if "1.12.2-14.23.5" not in name:
            print("Changing Directory for included forge installer")
            os.chdir(f"{this_dir}/{folder_name}")
            print("Running Forge Installer. This may take a minute or two...")
            os.system(f"java -jar {name} --installServer")
            print("Finished running forge installer")
            os.remove(name)
            print("Removed forge installer")
            try:
                os.remove(name + ".log")
                print("Removed forge installer log")
            except:
                pass
        if "1.12.2-14.23.5" in name:
            print("Found outdated and broken version of Forge 1.12.2. Downloading newest.")
            os.remove(name)
            twelvetwoforge = "https://maven.minecraftforge.net/net/minecraftforge/forge/1.12.2-14.23.5.2855/forge-1.12.2-14.23.5.2855-installer.jar"
            print("Changing Directory for downloading forge installer")
            os.chdir(f"{this_dir}/{folder_name}")
            forge_installer_dl = download(twelvetwoforge)
            forge_installer_dl_path = os.path.join(this_dir, folder_name, forge_installer_dl)
            print("Running Forge Installer. This may take a minute or two...")
            os.system(f"java -jar {forge_installer_dl_path} --installServer")
            os.remove(forge_installer_dl_path)
            print("Removed forge installer")
            try:
                os.remove(forge_installer_dl_path + ".log")
                print("Removed forge installer log")
            except:
                pass

#Check if fabric installer exists in serverpack dir. If does, run it.
fabric_installer = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*fabric*installer*.jar"):
    if name:
        fabric_installer = True
        print("Changing Directory for included fabric installer")
        os.chdir(f"{this_dir}/{folder_name}")
        print("Running Fabric Installer. This may take a minute or two...")
        os.system(f"java -jar {name} server -downloadMinecraft") #Downloads the minecraft server version as well with -downloadMinecraft
        print("Finished running fabric installer")
        os.remove(name)
        print("Removed fabric installer")
        try:
            os.remove(name + ".log")
            print("Removed fabric installer log")
        except:
            pass
renamed_serverjar = False
if fabric_installer:
    try:
        move("server.jar", "vanilla.jar")
        print("Renamed server.jar to vanilla.jar")
    except:
        pass
    try:
        move("fabric-server-launch.jar", "server.jar")
        renamed_serverjar = True
        print("Renamed fabric-server-launch.jar to server.jar")
    except:
        pass
    try:
        os.system('echo serverJar=vanilla.jar > fabric-server-launcher.properties')
        print("Changed fabric-server-launcher jar to downloaded vanilla.jar")
    except:
        pass

#Check if serverstarter installer exists in serverpack dir. If does, run it.
serverstarter_installer = False
serverstarter_fabric = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*.yaml"):
    if name:
        serverstarter_installer = True
        serverstarter_installpath = f"{this_dir}/{folder_name}/"
        print("Changing serverstarter install path to modpack directory")
        change_installpath(name, serverstarter_installpath) # Changes the installpath of the serverstarter script to base directory instead of the default /setup

        if operating_system == "Windows":
            file_ext = "*.bat"
            print("Detected Windows Operating System")
        if operating_system == "Linux":
            file_ext = "*.sh"
            print("Detected Linux Operating System")
        if operating_system == "Mac OS":
            file_ext = "*.sh"
            print("Detected Mac OS Operating System")
        for file in glob.glob(this_dir + "/" + folder_name + "/" + f"{file_ext}"):
            print("Changing Directory for serverstarter installer")
            os.chdir(f"{this_dir}/{folder_name}")
            print("Running Serverstarter Installer. This may take a minute or two...")
            if file_ext == "*.sh":
                os.system(f"chmod +x {file}")
            p = subprocess.Popen(f"{file}", stdout=subprocess.PIPE, shell=True)
            for line in p.stdout:
                print(line.decode())
                if b"fabric-server-launch.jar" in line:
                    serverstarter_fabric = True
                if b"The server installed successfully" in line or b"Done installing loader" in line or b"deleting installer" in line or b"EULA" in line or b"eula" in line:
                    print("Got Installer Finished Message")  # Terminates script when script has successfully installed all mods and forge files etc. and stops it from running the server
                    break
            kill(p.pid)
            print("Terminated serverstarter installer")
            print("Deleting leftover serverstarter installer file")
            os.remove(file)

if serverstarter_fabric:
    try:
        move("server.jar", "vanilla.jar")
        print("Renamed server.jar to vanilla.jar")
    except:
        pass
    try:
        move("fabric-server-launch.jar", "server.jar")
        renamed_serverjar = True
        print("Renamed fabric-server-launch.jar to server.jar")
    except:
        pass
    try:
        os.system('echo serverJar=vanilla.jar > fabric-server-launcher.properties')
        print("Changed fabric-server-launcher jar to downloaded vanilla.jar")
    except:
        pass

if (forge_installer or serverstarter_installer or fabric_installer) and not renamed_serverjar:
    server_jar_found = False
    for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*"):
        if "server.jar" in name:
            print(name)
            server_jar_found = True
            sever_jar_path = name
    if server_jar_found:
            print("Found old server.jar file. Deleting.")
            os.remove(sever_jar_path)

# manifest_installer = False
# if not forge_installer and not serverstarter_installer:
#     for name in glob.glob(this_dir + "/" + folder_name + "/" + "manifest.json"):
#         if name:
#             manifest_installer = True
#             print("Running manifest installer...")
#             os.system(f"python {this_dir}/curse_downloader.py --manifest {this_dir}/{folder_name}/manifest.json --nogui")

#If there was no included forge/fabric or serverstarter installer, as well as no manifest.json provided in the serverpack, get the manifest file and download the correct forge/fabric version and install it.
forge_or_fabric_file_found = False
server_jar_found = False
if not forge_installer and not serverstarter_installer and not fabric_installer:
    print("Neither a forge installer or a serverstarter installer was found for the downloaded pack. Checking if forge jar already exists...")
    for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*"):
        if "server.jar" in name:
            server_jar_found = True
            sever_jar_path = name
            print("Found Server Jar.")

    if server_jar_found:
        print("Found old server.jar.")
        os.remove(sever_jar_path)

    if not forge_or_fabric_file_found:
        manifest_file_found = False
        print("No forge or fabric file found. Checking for manifest.json...")
        for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "manifest.json"):
            if name:
                manifest_file_found = True
                print("Found manifest file in modpack folder. Grabbing forge or fabric version...")
                grabbed_manifest_version = get_forge_or_fabric_version_from_manifest(name)
                modpack_jar_type = grabbed_manifest_version[0]
                modpack_jar_version = grabbed_manifest_version[1]

        if not manifest_file_found:
            print("No manifest.json was found. Checking for it with normal downloadurl link...")
            filename = download(modpack_normal_downloadurl)
            temp_folder = unzip(filename, "manifest_check")
            for name in glob.glob(glob.escape(this_dir + "/" + temp_folder + "/") + "manifest.json"):
                if name:
                    print("Found manifest.json file in normal (non-serverpack) folder. Grabbing forge or fabric version...")
                    grabbed_manifest_version = get_forge_or_fabric_version_from_manifest(name)
                    modpack_jar_type = grabbed_manifest_version[0]
                    modpack_jar_version = grabbed_manifest_version[1]
                    delete_tree_directory(this_dir + "/" + temp_folder)
                    print("Deleted temp folder")

        if modpack_jar_type == "forge":
            if "1.12.2-14.23.5" in modpack_jar_version:
                print("Found outdated and broken version of forge 1.12.2. Downloading latest for 1.12.2 instead.")
                forge_installer_url = 'https://maven.minecraftforge.net/net/minecraftforge/forge/1.12.2-14.23.5.2855/forge-1.12.2-14.23.5.2855-installer.jar'
            else:
                forge_installer_url = f'https://files.minecraftforge.net/maven/net/minecraftforge/forge/{modpack_jar_version}/forge-{modpack_jar_version}-installer.jar'
            os.chdir(f"{this_dir}/{folder_name}")
            filename = download(forge_installer_url)
            for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + filename):
                if name:
                    print("Changing Directory to not-included forge installer")
                    os.chdir(f"{this_dir}/{folder_name}")
                    print("Running Forge Installer. This may take a minute or two...")
                    os.system(f'java -jar "{name}" --installServer')
                    print("Finished running forge installer")
                    os.remove(name)
                    print("Removed forge installer")
                    try:
                        os.remove(name + ".log")
                        print("Removed forge installer log")
                    except:
                        pass
        if modpack_jar_type == "fabric":
            fabric_installer_url = 'https://maven.fabricmc.net/net/fabricmc/fabric-installer/0.10.2/fabric-installer-0.10.2.jar' #! Will manually have to be changed as there is no hosted link to always get the latest fabric loader
            os.chdir(f"{this_dir}/{folder_name}")
            filename = download(fabric_installer_url)
            for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + filename):
                print(name)
                if name:
                    print("Changing Directory to not-included fabric installer")
                    os.chdir(f"{this_dir}/{folder_name}")
                    print("Running Fabric Loader. This may take a minute or two...")
                    os.system(f'java -jar "{name}" server -mcversion {modpack_jar_version} -downloadMinecraft')
                    print("Finished running Fabric Loader")
                    os.remove(name)
                    print("Removed Fabric Loader jar")
                    try:
                        move("server.jar", "vanilla.jar")
                        print("Renamed server.jar to vanilla.jar")
                    except:
                        pass
                    try:
                        move("fabric-server-launch.jar", "server.jar")
                        renamed_serverjar = True
                        print("Renamed fabric-server-launch.jar to server.jar")
                    except:
                        pass
                    try:
                        os.system('echo serverJar=vanilla.jar > fabric-server-launcher.properties')
                        print("Changed fabric-server-launcher jar to renamed vanilla.jar")
                    except:
                        pass


#Garbage files cleanup
print("Running garbage cleanup...")
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*installer.jar"):
    if name:
        print("Removing", name)
        os.remove(name)
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*.log"):
    if name:
        os.remove(name)
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*download.zip"):
    if name:
        print("Removing", name)
        os.remove(name)
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*.yaml"):
    if name:
        print("Removing", name)
        os.remove(name)
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "serverstarter*"):
    if name:
        print("Removing", name)
        os.remove(name)

if clean_startup_script == True: # If set to true, script will delete provided server startup script (.sh for linux and .bat for Windows).
    for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*.sh"):
        if name:
            if "run.sh" not in name:
                print("Removing", name)
                os.remove(name)
    for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "*.bat"):
        if name:
            if "run.bat" not in name:
                print("Removing", name)
                os.remove(name)
# for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "manifest.json"):
#     if name:
#         print("Removing", name)
#         os.remove(name)

for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "forge*.jar"):
    if name:
        print("Renaming", name, "to server.jar")
        os.chdir(f"{this_dir}/{folder_name}")
        os.rename(name, "server.jar")

has_properties = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "server.properties"):
    if name:
        has_properties = True
        print("server.properties file already found. Skipping download.")
if not has_properties:
    try:
        print("No server.properties file was found. Downloading...")
        download('https://raw.githubusercontent.com/parkervcp/eggs/master/minecraft/java/server.properties')
    except:
        pass

has_eula = False
for name in glob.glob(glob.escape(this_dir + "/" + folder_name + "/") + "eula.txt"):
    if name:
        has_eula = True
        print("eula.txt file already found. Skipping download.")
if not has_eula:
    try:
        print("No eula.txt file was found. Downloading...")
        download("https://raw.githubusercontent.com/kaboomserver/server/master/eula.txt")
    except:
        pass

# Forge 1.17+ section with new startup mechanism for non-ptero (symlink after not moving files)
if not mode == "pterodactyl":
    new_forge_ver = False
    for user_jvm_args in glob.glob(glob.escape(this_dir + "/" ) + "user_jvm_args.txt"):
        if user_jvm_args:
            print("Detected user_jvm_args.txt file indicating newer forge version.")
            new_forge_ver = True
            if operating_system == "Linux":
                for name in glob.glob(glob.escape(this_dir + "/") + "run.sh"):
                    if name:
                        os.system(f"chmod +x {name}")
            for forge_ver_folder in glob.glob(glob.escape(this_dir + "/" + "libraries" + "/" + "net" + "/" + "minecraftforge" + "/" + "forge" + "/") + "*"):
                if forge_ver_folder:
                    forge_ver = os.path.basename(forge_ver_folder)
                    print("Forge version is:", forge_ver)

                    link_from = join(this_dir, "libraries", "net", "minecraftforge", "forge", forge_ver, "unix_args.txt")
                    link_to = join(this_dir, "unix_args.txt")

                    print(f"Creating symbolic link for unix_args.txt to root folder from {link_from} to {link_to}")

                    if operating_system == "Linux":
                        os.system(f"ln -sf {link_from} {link_to}")
                        #os.symlink(link_from, link_to)
                    elif operating_system == "Windows": # Requires enabling developer mode in windows 10.
                        os.symlink(link_from, link_to)


if mode == "pterodactyl":
    # For Pterodactyl eggs only
    sleep(3)
    os.chdir(this_dir)
    try:
        os.mkdir("modpack_folder")
        print("Created modpack_folder")
    except:
        print("Modpack_folder already exists.")
    modpack_folder_files = os.listdir(join(this_dir, folder_name))
    for f in modpack_folder_files:
        sleep(1)
        if os.path.isdir:
            try:
                delete_tree_directory(join(this_dir, "modpack_folder", f))
            except:
                pass
        if os.path.isfile:
            try:
                os.remove(join(this_dir, "modpack_folder", f))
            except:
                pass
        try:
            move(join(this_dir, folder_name, f), join(this_dir, "modpack_folder", f))
        except:
            sleep(2)
            move(join(this_dir, folder_name, f), join(this_dir, "modpack_folder", f))
    delete_directory(join(this_dir, folder_name))

    os.system("rsync -a /mnt/server/modpack_folder/ /mnt/server/")
    os.system("rm -rf /mnt/server/modpack_folder/*")
    os.system("rm -r /mnt/server/modpack_folder")
    os.system("rm /mnt/server/requirements.txt")

    # Forge 1.17+ section with new startup mechanism for ptero (symlink after moving files)
    new_forge_ver = False
    for user_jvm_args in glob.glob(glob.escape(this_dir + "/" ) + "user_jvm_args.txt"):
        if user_jvm_args:
            print("Detected user_jvm_args.txt file indicating newer forge version.")
            new_forge_ver = True
            if operating_system == "Linux":
                for name in glob.glob(glob.escape(this_dir + "/") + "run.sh"):
                    if name:
                        os.system(f"chmod +x {name}")
            for forge_ver_folder in glob.glob(glob.escape(this_dir + "/" + "libraries" + "/" + "net" + "/" + "minecraftforge" + "/" + "forge" + "/") + "*"):
                if forge_ver_folder:
                    forge_ver = os.path.basename(forge_ver_folder)
                    print("Forge version is:", forge_ver)

                    link_from = join(this_dir, "libraries", "net", "minecraftforge", "forge", forge_ver, "unix_args.txt")
                    link_to = join(this_dir, "unix_args.txt")

                    #print(f"Creating symbolic link for unix_args.txt to root folder from {link_from} to {link_to}")

                    if operating_system == "Linux":
                        os.system(f"ln -sf {link_from} {link_to}")
                        #os.symlink(link_from, link_to)
                    elif operating_system == "Windows": # Requires enabling developer mode in windows 10.
                        os.symlink(link_from, link_to)

    if new_forge_ver:
        print("Changing startup script to work with new Forge startup")
        current_server_id = get_server_id(server_uuid, panel_url, application_api_key)
        update_new_forge(current_server_id, minecraft_version, panel_url, application_api_key)





print("Finished downloading and installing modpack", modpack_name + "! :)")


