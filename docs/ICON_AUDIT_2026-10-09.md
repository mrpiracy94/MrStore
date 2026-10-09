# Auditoria de ícones do MrStore — 2026-10-09

## Origem da auditoria

Inventário de `gh-pages/index.json` com 254 aplicações. O catálogo publicado tinha:

- **165** ícones não provisórios na listagem;
- **89** ícones apontados para `/assets/icon.svg` gerados a partir dos `Apps/*/icon.svg` provisórios;
- **25** das 89 aplicações com fonte externa real e fixada a uma revisão, já documentada em [ICON_SOURCES.md](../ICON_SOURCES.md) e confirmada pela miniatura WebP no catálogo;
- **64** aplicações ainda sem fonte real verificada nesta ronda.

## Correção incluída

Remover os 25 ficheiros `Apps/<app>/icon.svg` provisórios que se sobrepunham aos logótipos reais de `x-casaos.icon`. Os manifestos já apontam para os mesmos logótipos em `icon` e `thumbnail`; o builder ZimaOS poderá assim publicar o ativo correto em ambos os campos.

Nenhuma definição Docker é alterada: serviços, imagens, volumes, portas, redes e variáveis mantêm-se iguais.

## Ainda por verificar (64)

- `altus`
- `ardour`
- `azahar`
- `bitcoin-knots`
- `blade-of-agony`
- `budge`
- `calligra`
- `cops`
- `darktable`
- `dogwalk`
- `dosbox-staging`
- `duckstation`
- `eden`
- `faster-whisper`
- `ffmpeg`
- `flycast`
- `github-desktop`
- `gitqlient`
- `gzdoom`
- `habridge`
- `helium`
- `hishtory-server`
- `kdenlive`
- `kicad`
- `krita`
- `limnoria`
- `lm-studio`
- `luanti`
- `mame`
- `melonds`
- `minisatip`
- `modmanager`
- `mysql-workbench`
- `ngircd`
- `openshot`
- `openssh-server`
- `pcsx2`
- `pelorus`
- `pidgin`
- `ppsspp`
- `pycharm`
- `rawtherapee`
- `retroarch`
- `rpcs3`
- `rsnapshot`
- `scummvm`
- `sealskin`
- `shadps4`
- `shotcut`
- `socket-proxy`
- `spotube`
- `steamos`
- `swag`
- `syslog-ng`
- `unifi-network-application`
- `vlc`
- `webcord`
- `webgrabplus`
- `webstation`
- `weixin`
- `winegui`
- `wps-office`
- `xemu`
- `yaak`

## Validação após publicação

1. Compilar com `IceWhaleTech/build-appstore-action@v1` e verificar `dist/index.json` (254 entradas).
2. Verificar que os 25 ícones deste lote deixam de apontar para `/assets/icon.svg` provisório.
3. Confirmar em ZimaOS após atualização da loja; renovar a cache local se a interface continuar a apresentar o SVG antigo.
4. Não substituir os 64 ícones pendentes por imagens de aplicações parecidas sem confirmar a identidade e os direitos de utilização.
