import urllib.request
html=urllib.request.urlopen('https://www.mongodb.com/careers/jobs/8075467').read().decode('utf-8')
print('iframe' in html.lower())
print('greenhouse.io' in html.lower())
