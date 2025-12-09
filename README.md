# PyNetWizard
Graficzny konfigurator urządzeń sieciowych w ramach pracy inżynierskiej

## Setup

1. Jeśli testujemy program na GNS3 musimy utworzyć interfejs tantap. Służy do tego skrypt `setup-tantap`:

```shell
sudo ./setup-tantap
```

2. Uruchamiamy program za pomocą `uv`:

```shell
uv sync
uv run ./main.py
```