# Wi-Fi do MacBookPro14,3 no Linux

Ferramenta reversível para a **Broadcom BCM43602 do MacBook Pro de 15 polegadas de 2017**. Usa o driver `brcmfmac` e o firmware já fornecidos pelo Ubuntu, acrescentando uma configuração de placa obtida de uma fonte comunitária com revisão e hash fixados.

**Versão 0.1.0, experimental. Testada em uma única máquina:** MacBookPro14,3, Ubuntu Live 26.04.1 com persistência, kernel 7.0.0-30-generic, Alemanha. Outros modelos e identificadores de placa são recusados. Reinicialização, suspensão e uso prolongado ainda precisam ser verificados.

No teste, a configuração completa habilitou 5 GHz e elevou o sinal reportado de aproximadamente −80 para −40 a −44 dBm. A taxa de enlace chegou a 300–400 Mb/s; um download externo de 10 MB mediu 77,6 Mb/s. Os 20 pings ao roteador responderam sem perdas. Esses números não garantem o mesmo desempenho em outras máquinas. Não houve download comparável antes da mudança.

## Instalação

Baixe um arquivo em [Releases](https://github.com/mandatti/macbookpro143-wifi-linux/releases), extraia e abra o terminal dentro da pasta, ou clone:

```bash
git clone https://github.com/mandatti/macbookpro143-wifi-linux.git
cd macbookpro143-wifi-linux
``` Consulte os detalhes em [inglês](README.md) e os [créditos da configuração externa](THIRD_PARTY.md).

No Ubuntu, instale as dependências que faltarem:

```bash
sudo apt install python3 iw kmod network-manager tzdata ca-certificates linux-firmware
```

Informe o país onde está usando o equipamento. O exemplo usa `DE`, Alemanha; somente esse país foi testado.

```bash
./install.sh --country DE --dry-run
sudo ./install.sh --country DE
```

A instalação salva os arquivos anteriores e prepara a configuração. Reinicie para ativar. Para aplicar imediatamente:

```bash
sudo ./install.sh --country DE --apply
```

`--apply` interrompe o Wi-Fi enquanto recarrega o driver. Execute no próprio computador, não por uma sessão SSH dependente desse Wi-Fi. Se a rede ainda não estiver configurada, use o menu Wi-Fi do Ubuntu. A ferramenta não pede senha da rede nem credenciais do GitHub.

No Live USB, a persistência precisa estar funcionando. A ferramenta não altera o firmware binário, macOS, EFI ou o kernel. Os parâmetros de calibração vêm da comunidade; não são uma extração de fábrica desta unidade.

O instalador baixa a configuração externa e confere seu SHA-256. Sem internet, use `--nvram-source /caminho/arquivo.txt` com a cópia exata da revisão indicada em [THIRD_PARTY.md](THIRD_PARTY.md).

## Pacote .deb

Instalar o `.deb` somente disponibiliza a ferramenta. A configuração é aplicada explicitamente:

```bash
sudo apt install ./macbookpro143-wifi_0.1.0_all.deb
sudo macbookpro143-wifi install --country DE --apply
```

## Diagnóstico e reversão

```bash
python3 macbook_wifi.py diagnose
sudo ./uninstall.sh --apply
```

Com o `.deb`:

```bash
macbookpro143-wifi diagnose
sudo macbookpro143-wifi uninstall --apply
```

Sem `--apply`, reinicie após desinstalar. Os arquivos anteriores à primeira instalação são restaurados. Alterações manuais em arquivos gerenciados fazem a desinstalação parar antes de tocar neles. Uma falha de reconexão não desinstala automaticamente: a rede pode precisar ser escolhida no menu. Veja a [recuperação manual](docs/technical-notes.md#recovery).

Execute a reversão antes de remover o `.deb`; remover apenas o pacote não reverte a configuração do Wi-Fi.

O diagnóstico oculta SSID, MAC e IPv4. Revise a saída antes de compartilhar. Não publique senhas ou números de série. A ferramenta pode gerar um MAC local persistente quando encontra o endereço de exemplo do driver; nesse caso, reservas DHCP e filtros de MAC do roteador podem precisar de atualização.

Scripts e documentação originais sob licença MIT; os arquivos externos mantêm suas próprias condições. Créditos a MikeRatcliffe e à comunidade mbp-2016-linux.
