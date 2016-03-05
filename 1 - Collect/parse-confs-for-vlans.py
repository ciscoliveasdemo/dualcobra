#!/usr/bin/python

import re
from ipaddress import *

outfilename="switch-vlans.csv"

fields = ['vlan_name','vlan_ip','vlan_mask','vlan_vrrp_ip','vlan_vdom']

def read_file_to_list(fname):
    with open(fname,'U') as fh:
        return [line.rstrip("\n") for line in fh]

def write_list_to_file(fname,list):
    with open(fname,'w') as fh:
        fh.write('\n'.join(list))

switches=['dc1-sw1','dc1-sw2','dc2-sw1','dc2-sw2']
all_devices=switches + ['fw']

vlans={		
	"dc1-sw1":{"file":read_file_to_list("DC1-SW1-Config.txt")}, 
	"dc1-sw2":{"file":read_file_to_list("DC1-SW2-Config.txt")},
	"dc2-sw1":{"file":read_file_to_list("DC2-SW1-Config.txt")},
	"dc2-sw2":{"file":read_file_to_list("DC2-SW2-Config.txt")},
	"fw":{"file":read_file_to_list("Firewall-Config.txt")}
}


for switch_name in all_devices:
    vlans[switch_name]["vlans"]=dict()

for switch_name in switches:
    for line in vlans[switch_name]["file"]:
        if re.search(r"configure vlan ([\-\w]+) tag (\d+)",line):
            vlan_name=re.search(r"configure vlan ([\-\w]+) tag (\d+)",line).group(1)
            vlan_id=re.search(r"configure vlan ([\-\w]+) tag (\d+)",line).group(2)
            for switch_name_2 in all_devices:
                if not vlans[switch_name_2]["vlans"].get(vlan_id):
                    vlans[switch_name_2]["vlans"][vlan_id]=dict()
                    for f in fields:
                        vlans[switch_name_2]["vlans"][vlan_id][f]=""
            vlans[switch_name]["vlans"][vlan_id]["vlan_name"]=vlan_name
            for line in vlans[switch_name]["file"]:
                if re.search(r"configure vlan %s ipaddress ([\d\.]+) ([\d\.]+)"%vlan_name,line,re.IGNORECASE):
                    vlans[switch_name]["vlans"][vlan_id]["vlan_ip"]=re.search("configure vlan %s ipaddress ([\d\.]+) ([\d\.]+)" % vlan_name, line, re.IGNORECASE).group(1)
                    vlans[switch_name]["vlans"][vlan_id]["vlan_mask"]=re.search("configure vlan %s ipaddress ([\d\.]+) ([\d\.]+)" % vlan_name, line, re.IGNORECASE).group(2)
                if re.search(r"configure vrrp vlan %s vrid \d+ add ([\d\.]+)"%vlan_name,line,re.IGNORECASE):
                    vlans[switch_name]["vlans"][vlan_id]["vlan_vrrp_ip"]=re.search(r"configure vrrp vlan %s vrid \d+ add ([\d\.]+)" % vlan_name, line, re.IGNORECASE).group(1)

fg=vlans["fw"]["file"]
int_conf=dict()
n=0
startn=0
endn=0
starti=0
endi=0
while n<len(fg):
    n=n+1
    if startn==0:
        if re.search(r"config system interface",fg[n]):
            startn=n
            continue
    else:
        if re.search(r"end",fg[n]):
            endn=n
            break
        if starti==0:
            if re.search(r'edit "[\-\w]+"',fg[n]):
                starti=n
                int_name=re.search(r'edit "([\-\w]+)"',fg[n]).group(1)
                int_conf[int_name]=dict()
        else:
            if re.search(r"next",fg[n]):
                endi=n
                starti=0
                if int_conf[int_name].get("vlanid"):
                    vlan_id=int_conf[int_name]["vlanid"]
                    for switch_name_2 in all_devices:
                        if not vlans[switch_name_2]["vlans"].get(vlan_id):
                            vlans[switch_name_2]["vlans"][vlan_id]=dict()
                            for f in fields:
                                vlans[switch_name_2]["vlans"][vlan_id][f]=""
                    vlans["fw"]["vlans"][vlan_id]["vlan_name"]=int_name
                    vlans["fw"]["vlans"][vlan_id]["vlan_ip"]=int_conf[int_name]["ip"]
                    vlans["fw"]["vlans"][vlan_id]["vlan_mask"]=int_conf[int_name]["mask"]
                    vlans["fw"]["vlans"][vlan_id]["vlan_vdom"]=int_conf[int_name]["vdom"]
                continue
            else:
                if re.search(r'set [\w\-]+ "?[\.\w\-]+"?',fg[n]):
                    k=re.search(r'set ([\w\-]+) "?([\.\w\-]+)"?',fg[n]).group(1)
                    v=re.search(r'set ([\w\-]+) "?([\.\w\-]+)"?',fg[n]).group(2)
                    int_conf[int_name][k]=v
                    if k=="ip":
                        int_conf[int_name]["mask"]=re.search(r'set [\w\-]+ [\.\w\-]+ ([\.\w\-]+)',fg[n]).group(1)
                else:
                    print "Can't parse",fg[n]
                    exit(1)

outfileheadings= [ "sw_vlan_name", "fw_vlan_name", "vlan_id", "vlan_in_DC1", "vlan_in_DC2", "vlan_in_fw", "dc1_sw1_ip", "dc1_sw2_ip", "dc2_sw1_ip", "dc2_sw2_ip", "DC1_vrrp_ip", "DC2_vrrp_ip", "vrrp_ips_match", "fw_vdom", "fw_ip", "vlan_subnet" ]
outfilelist=[ ','.join(outfileheadings) ]

all_vlan_ids=set()
for switch_name in switches:
    all_vlan_ids = set( list(all_vlan_ids) + vlans[switch_name]["vlans"].keys() )

for vlan_id in all_vlan_ids:
    vlan_names_set=set()
    for switch_name in switches:
        sw_vlan_name=vlans[switch_name]["vlans"][vlan_id]["vlan_name"]
        if sw_vlan_name!="":
            vlan_names_set.add(sw_vlan_name)
        if len(vlan_names_set)>1:
            print "Vlan Name mismatch!"
            exit (1)
    if len(vlan_names_set)==1:
        sw_vlan_name=vlan_names_set.pop()
    else:
        sw_vlan_name=""
    fw_vlan_name=vlans["fw"]["vlans"][vlan_id].get("vlan_name")

    vrrp_ips_set=set()

    vrrp_ip_dc1_sw1=vlans["dc1-sw1"]["vlans"][vlan_id]["vlan_vrrp_ip"]
    vrrp_ip_dc1_sw2=vlans["dc1-sw2"]["vlans"][vlan_id]["vlan_vrrp_ip"]
    vrrp_ip_dc2_sw1=vlans["dc2-sw1"]["vlans"][vlan_id]["vlan_vrrp_ip"]
    vrrp_ip_dc2_sw2=vlans["dc2-sw2"]["vlans"][vlan_id]["vlan_vrrp_ip"]

    if vrrp_ip_dc1_sw1!=vrrp_ip_dc1_sw2 or vrrp_ip_dc2_sw1!=vrrp_ip_dc2_sw2:
        print "VRRP IP mismatch!"
        for switch_name in switches:
            print "Switch",switch_name,"vlan",vlan_name,"vrrp_ip",vlans[switch_name]["vlans"][vlan_id]["vlan_vrrp_ip"]
    vrrp_ip_DC1=vrrp_ip_dc1_sw1
    vrrp_ip_DC2=vrrp_ip_dc2_sw1

    if vrrp_ip_DC1=="" or vrrp_ip_DC2=="":
        vrrp_ips_match=""
    elif vrrp_ip_DC1==vrrp_ip_DC2:
        vrrp_ips_match="Y"
    else:
        vrrp_ips_match="N"

    vlan_name_dc1_sw1=vlans["dc1-sw1"]["vlans"][vlan_id]["vlan_name"]
    vlan_name_dc1_sw2=vlans["dc1-sw2"]["vlans"][vlan_id]["vlan_name"]
    vlan_name_dc2_sw1=vlans["dc2-sw1"]["vlans"][vlan_id]["vlan_name"]
    vlan_name_dc2_sw2=vlans["dc2-sw2"]["vlans"][vlan_id]["vlan_name"]
    vlan_name_fw=vlans["fw"]["vlans"][vlan_id]["vlan_name"]

    vlan_in_DC1=""
    vlan_in_DC2=""
    vlan_in_fw=""

    print"VLAN in site - ID",vlan_id
    for sw in switches:
        print "\tSwitch",sw,"vlan name",vlans[sw]["vlans"][vlan_id]["vlan_name"]
        print "\t",vlans[sw]["vlans"][vlan_id]

    if vlan_name_dc1_sw1!="" and vlan_name_dc1_sw1==vlan_name_dc1_sw2:
        vlan_in_DC1="Y"

    if vlan_name_dc2_sw1!="" and vlan_name_dc2_sw1==vlan_name_dc2_sw2:
        vlan_in_DC2="Y"

    if vlan_name_fw!="":
        vlan_in_fw="Y"

    if vlan_name_dc1_sw1!=vlan_name_dc1_sw2 and vlan_name_dc2_sw1==vlan_name_dc2_sw2=="":
        if vlan_name_dc1_sw1=="":
            vlan_in_DC1="dc1-sw2 only"
        elif vlan_name_dc1_sw2=="":
            vlan_in_DC1="dc1-sw1 only"
        else:
            print"VLAN mismatch within DC1 site - ID",vlan_id
            for sw in switches:
                print "\tSwitch",sw,"vlan name",vlans[sw]["vlans"][vlan_id]["vlan_name"]
            exit(1)

    if vlan_name_dc2_sw1!=vlan_name_dc2_sw2 and vlan_name_dc1_sw1==vlan_name_dc1_sw2=="":
        if vlan_name_dc2_sw1=="":
            vlan_in_DC2="dc2-sw2 only"
        elif vlan_name_dc2_sw2=="":
            vlan_in_DC2="dc2-sw1 only"
        else:
            print"VLAN mismatch within DC2 site - ID",vlan_id
            for sw in switches:
                print "\tSwitch",sw,"vlan name",vlans[sw]["vlans"][vlan_id]["vlan_name"]
            exit(1)

    if vlans["fw"]["vlans"][vlan_id]["vlan_name"]!="":
            vlan_in_fw="Y"

    vlan_masks_set=set()
    for switch_name in all_devices:
        vlan_mask=vlans[switch_name]["vlans"][vlan_id]["vlan_mask"]
        if vlan_mask!="":
            vlan_masks_set.add(vlan_mask)
        if len(vlan_masks_set)>1:
            print "VLAN Mask mismatch!"
            exit (1)
    if len(vlan_masks_set)==1:
        vlan_mask=vlan_masks_set.pop()

    dc1_sw1_ip=vlans["dc1-sw1"]["vlans"][vlan_id]["vlan_ip"]
    dc1_sw2_ip=vlans["dc1-sw2"]["vlans"][vlan_id]["vlan_ip"]
    dc2_sw1_ip=vlans["dc2-sw1"]["vlans"][vlan_id]["vlan_ip"]
    dc2_sw2_ip=vlans["dc2-sw2"]["vlans"][vlan_id]["vlan_ip"]
    fw_ip=vlans["fw"]["vlans"][vlan_id]["vlan_ip"]
    fw_vdom=vlans["fw"]["vlans"][vlan_id]["vlan_vdom"]

    vlan_ip=""
    vlan_subnet=""
    for ip in [ dc1_sw1_ip, dc1_sw2_ip, dc2_sw1_ip, dc2_sw2_ip, fw_ip ]:
        if ip!="" and ip:
            vlan_ip=ip
            break
    if vlan_ip!="":
        vlan_subnet=str(ip_network(unicode("%s/%s" % (vlan_ip, vlan_mask)),strict=False))

    linelist=[ sw_vlan_name, fw_vlan_name, vlan_id, vlan_in_DC1, vlan_in_DC2, vlan_in_fw, dc1_sw1_ip, dc1_sw2_ip, dc2_sw1_ip, dc2_sw2_ip, vrrp_ip_DC1, vrrp_ip_DC2, vrrp_ips_match, fw_vdom, fw_ip, vlan_subnet ]

    outfilelist.append(','.join( linelist))

write_list_to_file(outfilename,outfilelist)




