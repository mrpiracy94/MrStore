# HedgeDoc — plano de atualização segura (2026-10-10)

## Risco identificado
O manifest expõe agora DB_HOST e CMD_DOMAIN reais, substituindo nomes e domínios de exemplo. A imagem Docker, a porta pública 20029, a porta interna 3000 e o volume /DATA/AppData/hedgedoc/config permanecem iguais. Esta alteração NÃO instala um servidor MariaDB.

## Backup obrigatório
Antes de qualquer atualização numa instalação existente, parar o serviço, guardar a configuração, copiar todo o volume /DATA/AppData/hedgedoc/config para local seguro e guardar a definição Compose anterior. Fazer também um dump consistente da base de dados MariaDB/MySQL externa, com credenciais administrativas protegidas. Confirmar que é possível recuperar estes dados antes de editar o serviço.

## Migração e compatibilidade
Não existe migração de esquema de dados prevista nesta PR porque não há troca de imagem nem de DB. Se o HedgeDoc já funciona, não substituir à força o DB_HOST, o CMD_DOMAIN, nem as credenciais que estão a ser usadas. Preservar os valores existentes após o backup. Para novas instalações, criar primeiro MariaDB/MySQL com utilizador e permissões próprias, testar DNS/conectividade entre containers e definir DB_HOST, DB_USER, DB_PASS e DB_NAME, bem como CMD_DOMAIN/HTTPS/reverse proxy corretos. A porta 20029 do host deve manter-se igual ou exigir revisão da configuração externa de URLs e callbacks. Nunca instalar com CHANGE_ME.

## Testes (a realizar num ZimaOS real)
Após a migração ou criação da instalação de teste, confirmar arranque, login, criação e edição de uma nota fictícia, URLs de redirecionamento e persistência depois de reiniciar. Confirmar logs do container e ligação ao DB antes de declarar funcionamento. Estes testes ainda NÃO foram realizados num NAS.

## Rollback
Se aparecerem erros, parar a app, repor as variáveis e a versão anterior do Compose e restaurar /DATA/AppData/hedgedoc/config guardado. Caso alguma migração da base tenha ocorrido de forma externa, restaurar o dump no servidor de base de dados antes de reiniciar, sem sobrescrever a base atual sem confirmação. Não apagar o volume existente. Documentar a falha e manter a app fora de uma release segura até corrigida.

Referência: https://docs.linuxserver.io/images/docker-hedgedoc/
