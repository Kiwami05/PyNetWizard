# PyNetWizard
Graficzny konfigurator urządzeń sieciowych w ramach pracy inżynierskiej

## TODO

### Połączenie

- [x] Statyczne definiowanie hostów
- [x] Dynamiczne definiowanie hostów (coś jak nmap)
- [x] Zaciąganie hostów z pliku
- [x] Automatyczne rozpoznawanie typu urządzenia
- [x] Wielowątkowość — przy pobieraniu i wysyłaniu configa

### Ustawienia

- [x] Typ połączenia
- [ ] Timeout?

### Konfiguracja

- [ ] Wysyłanie configu dla pojedynczego urządzenia i dla wszystkich
- [ ] Eksport konfiguracji do pliku
    - [ ] Eksport do playbook-a Ansible?
- [ ] Import konfiguracji na urządzenie
    - [ ] Wersja rozszerzona — masowy import (konfig do playbooka Ansible i uruchamianie)
- [ ] Modyfikacja interfejsu sieciowego (Ethernet itd.)
- [ ] Historia zmian

#### Switch

- [ ] Trunk/access mode konfiguracja
- [ ] Konfiguracja vlan-ów

#### Router

- [ ] Routing
    - [ ] Statyczny
    - [ ] RIPv2
    - [ ] OSPF
- [ ] Podgląd tabeli routingu

#### Firewall

- [ ] ACL

### Pozostałe

- [ ] Konfiguracja urządzeń poprzez tunel — jeśli mamy hosty w sieciach A i B to chcemy móc konfigurować hosty w sieci B
  łącząc się poprzez host-a w sieci A
- [ ] Logi błędów
- [ ] Logowanie konsoli

### Propozycje

- Cache połączeń / sesji SSH
- Obsługa kluczy SSH i haseł (sejf haseł)
- Ping / traceroute na routerze
- Raport zbiorczy (np. w PDF/HTML) z konfiguracji wszystkich urządzeń