import subprocess
import requests

def sendReport(name):
    t = open("/proc/cpuinfo", "r").read()
    SN="Unknown"
    for l in t.split("\n"):
        if 'Serial' in l:
            SN = l[-8:]
    print("Serial: {}".format(SN))
    res = subprocess.run(['journalctl', '-u', name, '-n', '100'], stdout=subprocess.PIPE).stdout.decode('utf-8')
    if "Traceback" not in res:
        print("Skip sending report")
        return
    print("Sending report")
    headers = {'Content-Type': 'text/html', 'Accept-Charset': 'UTF-8'}
    content = "Serial: {}\n".format(SN)+res
    r = requests.post('https://repo.larnitech.com/serversLogs/crash.php?name='+name, data=content.encode('utf-8'), headers=headers)
    if r.status_code == requests.codes.ok:
        print("Report successfuly sent")
    else:
        print("Error sending report. Code: {}".format(r.status_code))
    return
