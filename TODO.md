# TODO

## NA DZIŚ

- [x] Walidacja wprowadzanych urządzeń
- [x] Radio Cisco czy Juniper
- [ ] Pingowanie urządzeń
- [ ] Wyczyść listę
- [ ] Usuń pojedyncze urządzenie
- [ ] Ustawienia i autołączenie się z urządzeniem w celu pobrania konfiga

## Połączenie

- [ ] Statyczne definiowanie hostów
- [ ] Dynamiczne definiowanie hostów (coś jak nmap)
- [ ] Zaciąganie hostów z pliku
- [ ] Auto-rozpoznawanie typu hosta (system operacyjny)
- [ ] Automatyczne rozpoznawanie typu urządzenia
- [ ] Ping hosta przed próbą logowania
- [ ] Wielowątkowość — wiele połączeń naraz (wątki lub async)

## Konfiguracja

- [ ] Tryb commit-ów jak w junos (przełącznik)
- [ ] Parametry wyświetlane w czasie rzeczywistym
- [ ] Eksport konfiguracji do pliku
    - [ ] Eksport do playbook-a Ansible?
- [ ] Import konfiguracji na urządzenie
    - [ ] Wersja rozszerzona — masowy import (konfig do playbooka Ansible i uruchamianie)
- [ ] Modyfikacja interfejsu
- [ ] Historia zmian

### Switch

- [ ] Trunk/access mode konfiguracja
- [ ] Konfiguracja vlan-ów

### Router

- [ ] Routing
    - [ ] Statyczny
    - [ ] RIPv2
    - [ ] OSPF
- [ ] Podgląd tabeli routingu

### Firewall

- [ ] ACL

## Pozostałe

- [ ] Konfiguracja urządzeń poprzez tunel — jeśli mamy hosty w sieciach A i B to chcemy móc konfigurować hosty w sieci B
  łącząc się poprzez host-a w sieci A
- [ ] Logi błędów
- [ ] Logowanie konsoli

## Propozycje

- Cache połączeń / sesji SSH
- Obsługa kluczy SSH i haseł (sejf haseł)
- Ping / traceroute na routerze
- Raport zbiorczy (np. w PDF/HTML) z konfiguracji wszystkich urządzeń