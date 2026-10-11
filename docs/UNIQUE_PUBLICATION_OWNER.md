# Único publicador automático do catálogo MrStore

Com 254 aplicações, a rotina legada de restauro de 233 apps e a antiga
retirada de SteamOS não podem publicar automaticamente. Passam a
funcionar apenas por acionamento manual, sujeitos aos seus próprios
testes de segurança e validação de dimensão.

A montra website passa a validar em push/PR sem escrever gh-pages.
A publicação completa em rollout-233.yml é o único fluxo automático
que escreve gh-pages em push de main. As atualizações de web/** já
desencadeiam essa publicação completa, preservando index.json,
security-inventory.json, release-status.json e os 254 manifestos.

A publicação manual e isolada do website continua disponível em
publish-storefront.yml, explicitamente via workflow_dispatch. O
controlo de concorrência mrstore-static-site mantém-se partilhado
para evitar escrita simultânea de arquivos incompatíveis.

Nota: alterações ao repositório não alteram instalações existentes.
O catálogo não é segurança-certificado apenas por ser publicado.
