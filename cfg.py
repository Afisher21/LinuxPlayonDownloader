import logging, os, configparser

g_iniPath = 'PlayonDownloader.ini'

# ExtendedInterpolation means ini can use ${} instead of %()s, and lets you refer to other sections besides default if needed
g_config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
g_config.read(g_iniPath)

g_paths = g_config['Paths']
g_creds = g_config['Credentials']
g_settings = g_config['Settings']
