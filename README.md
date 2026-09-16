# IcarusTexture

Resource pack experimental para **Minecraft Java 26.2**.

Este primeiro commit contém a prova de conceito V2 do **Miner Helmet**, uma textura de `player_head` que usa transparência real para remover o preenchimento cinza/azulado da cabeça sem apagar as tiras e os detalhes do capacete.

## Estrutura

```text
IcarusTexture/
├── pack.mcmeta
└── assets/
    └── icarus/
        └── textures/
            └── heads/
                └── miner_helmet.png
```

O identificador da textura é:

```text
icarus:heads/miner_helmet
```

## Teste no jogo

Instale o repositório como resource pack ou compacte o conteúdo da raiz em um arquivo ZIP. Ative o pack no Minecraft Java 26.2 e execute:

```mcfunction
/give @s minecraft:player_head[minecraft:profile={texture:"icarus:heads/miner_helmet"}]
```

Teste a cabeça no inventário, na mão, colocada no mundo e equipada pelo jogador. Esta textura ainda é uma prova de conceito e pode receber ajustes após a validação visual no jogo.

## Escopo atual

- Minecraft Java 26.2 (`pack_format` 88)
- namespace `icarus`
- textura V2 em PNG 64×64 com canal alpha
- somente arquivos-fonte do resource pack

Ainda não há versão Bedrock/Geyser nem pacote de release neste repositório.

## Referência da POC

A POC foi baseada na textura [Miner Helmet #26723](https://minecraft-heads.com/custom-heads/head/26723-miner-helmet), adaptada para testar transparência em uma textura local do resource pack.
