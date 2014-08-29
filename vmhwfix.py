#!/usr/bin/python -tt
# @author      William Leemans <willie@elaba.net>
# @changelog   2014-08-13 Start
#              2014-08-19 Removal and replacement of get_vmobj function to display the vSphere server a vm is found in

try:
  import getpass
except:
  print "The getpass module is required for this script to work."
  exit(1)

try:
  import paramiko
except:
  print "The paramiko module is required for this script to work."
  exit(1)

try:
  from pysphere import VIServer
except:
  print "The pysphere module is required for this script to work."
  exit(1)

try:
  from optparse import OptionParser
except:
  print "The optparse module is required for this script to work."
  exit(1)

try:
  from time import sleep
except:
  print "The time module is required for this script to work."
  exit(1)


vCenter = []
user = ""
password = ""
hosts = []
problem_keys = [ "virtualHW.scheduledUpgrade.when", "virtualHW.scheduledUpgrade.state", "tools.upgrade.policy" ]

class colors:
  yellow = '\033[93m'
  green  = '\033[92m'
  red    = '\033[91m'
  endc   = '\033[0m'


def main():
  global vCenter, user, password, problem_keys
  (options, args) = parse_args()
  vCenter = options.vsphere
  user = options.user
  password = getpass.getpass("Please provide the password for "+user+":")

  ssh = paramiko.SSHClient()
  ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

  svr = VIServer()

  for host in options.hostname:
    print colors.yellow+"Starting fix for "+host+colors.endc
    if options.pretend is True:
      print colors.green+"This system will not be harmed during the course of this script."
      print "Meaning: it will "+colors.red+"NOT"+colors.green+" be shutdown, changed, reloaded and powered on again."+colors.endc
    print ""
    print "Searching vCenter membership"
    vmobj = None
    for e in options.vsphere:
      svr.connect(e,options.user,password)
      try:
        vm = svr.get_vm_by_name(host)
        vCenterHost = e
        break
      except:
        vm = None

    if vm is None:
      print colors.red+"'"+host+"' could not be found on any of the vCenter servers. Aborting."+colors.endc
      continue
    else:
      print colors.green+"Found: "+vCenterHost+colors.endc

    print "Determining ESX host"
    try:
      temp = vm.properties
      esxhost = temp.runtime.host.name
    except:
      print colors.red+"Could not determine the physical host for '"+host+"'. Aborting."+colors.endc
      continue
    print colors.green+"Found:", esxhost, colors.endc

    print "Determining local path to vmx file"
    try:
      vmxpath = vm.get_property("path").replace("[","/vmfs/volumes/").replace("] ","/")
    except:
      print colors.red+"Could not determine the vmx file path for '"+host+"'. Aborting."+colors.endc
      continue
    print colors.green+"Found:", vmxpath, colors.endc

    print "Retrieving vmx file"
    try:
      ssh.connect(esxhost, username="root")
    except:
      print colors.red+"Could not connect to "+esxhost+" over ssh. Aborting."+colors.endc
      continue
    stdin, stdout, stderr = ssh.exec_command("cat "+vmxpath)
    out = stdout.read()
    print colors.green+"Done"+colors.endc

    print "Looking for problem keys"
    severity = 0
    for key in problem_keys:
      if key in out:
        print colors.yellow+"Found: "+key+colors.endc
        severity = severity +1

    print colors.green+"Done"+colors.endc

    if severity == 0:
      print colors.yellow+"None of the offending keys have been found"+colors.endc
      if options.force == False:
        print colors.red+"Aborting"+colors.endc
        continue

    if options.pretend is not True:
      print "Powering off the vm"
      try:
        if vm.get_status(basic_status=True) == 'POWERED ON':
          vm.shutdown_guest()
          count = 0
          ret = ''
          while ret != "POWERED OFF":
            sleep(1)
            ret = vm.get_status(basic_status=True)
            count = count +1
            if count > 300:
              print "The system did not gracefully shutdown. Please fix. Aborting all."
              exit(1)
        elif vm.get_status(basic_status=True) == 'POWERED OFF':
          print "The system is either already shutdown, or there are no vmware tools installed."
          raw_input("Press ENTER to continue or CTRL+C to abort")

      except:
        print colors.red+"Something went wrong powering off "+host+". Aborting."+colors.endc
        break
    else:
      print "Pretending to power off the vm"
    print colors.green+"Done."+colors.endc

    if options.pretend is not True:
      print "Modifying vmx file."
      cmd = "cp "+vmxpath+ " "+vmxpath+".hwfix;"
      cmd = cmd + "sed -i -e '/^virtualHW.scheduledUpgrade.when\\b/d' -e '/^virtualHW.scheduledUpgrade.state\\b/d' -e '/^tools.upgrade.policy\\b/d' "+vmxpath
      try:
        ssh.connect(esxhost, username="root")
        stdin, stdout, stderr = ssh.exec_command(cmd)
      except:
        print colors.red+"Could not connect to "+esxhost+" over ssh. Aborting."+colors.endc
        break
    else:
      print "Pretending to modify the vmx file."
    print colors.green+"Done."+colors.endc

    if options.pretend is not True:
      print "Reloading the vm's config file."
      vm.reload()
    else:
      print "Pretending to reloading the vm's config file."
    print colors.green+"Done."+colors.endc

    if options.pretend is not True:
      print "Starting the vm."
      try:
        sleep(5)
        vm.power_on()
      except:
        print colors.red+"Something went wrong powering on "+host+". Aborting."+colors.endc
        continue
    else:
      print "Pretending to start the vm."
   print colors.green+"Done"+colors.endc
    print ""
    print colors.green+host+" is fixed."+colors.endc
    if options.pretend is True:
      print colors.green+"But not really..."+colors.endc
    print ""

def parse_args():
  parser = OptionParser()
  parser.add_option("-s", "--vsphere", dest='vsphere', help='hostname(s) of the vSphere servers to connect to. Separate using a colon (:)', action='store', type='string', default='none')
  parser.add_option("-U", "--user", dest='user', help='username to use to connect to the vSphere server', action='store', type='string', default='none')

  parser.add_option("-n", "--hostname", dest='hostname', help='hostname of the server to be fixed (multiple can be sperated by colon [:])', action='store', type='string', default='none')

  parser.add_option("-f", "--force", dest='force', help='Perform the fix, even if the offending keys haven\'t been found', action='store_true', default=False)
  parser.add_option("-p", "--pretend", dest='pretend', help='Don\' actually perform actions.', action='store_true', default=False)

  (options, args) = parser.parse_args()
  if options.hostname == "none":
    parser.error("You must specify at least one hostname. Multiple hostnames can be separated by a colon (:)")
  if options.vsphere == "none":
    parser.error("You must specify at least one vSphere hostname. Multiple vSphere hostnames can be separated by a colon (:)")
  if options.user == "none":
    parser.error("You must specify the username to connect to the vSphere server(s)")
  options.vsphere    = options.vsphere.split(':')
  options.hostname   = options.hostname.split(':')


  return (options, args)


if __name__ == '__main__':
  main()

