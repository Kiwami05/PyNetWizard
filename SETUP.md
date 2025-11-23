## Router Cisco

```
Router(config)# hostname CISCO-R1
CISCO-R1(config)# enable secret cisco
CISCO-R1(config)# ip domain-name gns-lab
CISCO-R1(config)# username admin secret cisco

CISCO-R1(config)# interface GigabitEthernet1
CISCO-R1(config-if)# ip address 10.0.0.11 255.255.255.0
CISCO-R1(config-if)# no shutdown

CISCO-R1(config)# crypto key generate rsa modulus 2048
CISCO-R1(config)# ip ssh version 2
CISCO-R1(config)# line vty 0 15
CISCO-R1(config-line)# transport input ssh
CISCO-R1(config-line)# login local

CISCO-R1#write
```

## Switch Cisco

```
Switch(config)#hostname CISCO-SW1
CISCO-SW1(config)#enable secret cisco
CISCO-SW1(config)#ip domain-name gns-lab
CISCO-SW1(config)#username admin privilege 15 secret cisco
CISCO-SW1(config)#service password-encryption

CISCO-SW1(config)#vlan 10
CISCO-SW1(config-vlan)#name MGMT
CISCO-SW1(config)#interface Vlan10
CISCO-SW1(config-if)#ip address 10.0.0.12 255.255.255.0
CISCO-SW1(config-if)#no shutdown

CISCO-SW1(config)#interface GigabitEthernet0/0
CISCO-SW1(config-if)#switchport mode access
CISCO-SW1(config-if)#switchport access vlan 10
CISCO-SW1(config-if)#no shutdown

CISCO-SW1(config)#ip default-gateway 10.0.0.1
CISCO-SW1(config)#crypto key generate rsa modulus 2048
CISCO-SW1(config)#ip ssh version 2
CISCO-SW1(config)#ip ssh time-out 60
CISCO-SW1(config)#ip ssh authentication-retries 3

CISCO-SW1(config)#line vty 0 15
CISCO-SW1(config-line)#transport input ssh
CISCO-SW1(config-line)#login local
CISCO-SW1(config-line)#exec-timeout 0 0

CISCO-SW1#write
```