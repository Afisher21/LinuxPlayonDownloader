import os, logging, configparser

g_iniPath = 'PlayonDownloader.ini'

# ExtendedInterpolation means ini can use ${} instead of %()s, and lets you refer to other sections besides default if needed
g_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
g_config.read(g_iniPath)

g_paths = g_config['Paths']
g_creds = g_config['Credentials']
g_settings = g_config['Settings']

logging.basicConfig(filename=os.path.join(g_paths['mediaroot'], g_settings['logfile']), level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

logging.debug('RemoveFailedDownloads invoked')

to_delete = []
download_folder = g_paths['downloadfolder']
for file in os.listdir(download_folder):
    if file.endswith('crdownload'):
        to_delete.append(file)

if len(to_delete) > 0:
    logging.info('Failed downloads to remove: ' + str(to_delete))

for file in to_delete:
    os.remove(os.path.join(download_folder, file))