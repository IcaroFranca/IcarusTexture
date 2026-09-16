# IcarusTexture

Resource pack do IcarusRPG para **Minecraft Java 26.2**.

O **Miner Helmet** usa uma textura de `player_head` com transparência real para remover o preenchimento cinza/azulado da cabeça sem apagar as tiras e os detalhes do capacete.

A **Undead's Sword** usa um item model customizado (16×16) aplicado pelo IcarusRPG via componente `minecraft:item_model`.

## Estrutura

```text
IcarusTexture/
├── pack.mcmeta
└── assets/
    └── icarus/
        ├── textures/
        │   ├── heads/
        │   │   └── miner_helmet.png
        │   └── item/
        │       └── undead_sword.png
        ├── items/
        │   └── undead_sword.json
        └── models/
            └── item/
                └── undead_sword.json
```

O identificador da textura da cabeça é:

```text
icarus:heads/miner_helmet
```

O identificador do item model da espada é:

```text
icarus:undead_sword
```

## Teste no jogo

Instale o repositório como resource pack ou compacte o conteúdo da raiz em um arquivo ZIP. Ative o pack no Minecraft Java 26.2 e execute:

```mcfunction
/give @s minecraft:player_head[minecraft:profile={texture:"icarus:heads/miner_helmet"}]
/give @s minecraft:iron_sword[minecraft:item_model="icarus:undead_sword"]
```

Teste a cabeça no inventário, na mão, colocada no mundo e equipada pelo jogador. Teste a espada no inventário e na mão.

## Escopo atual

- Minecraft Java 26.2 (`pack_format` 88)
- namespace `icarus`
- textura V2 da cabeça em PNG 64×64 com canal alpha; textura da espada em PNG 16×16 com canal alpha
- arquivos-fonte e releases prontas para uso obrigatório pelo servidor

O fallback Bedrock/Geyser do Miner Helmet é fornecido pelo IcarusRPG em Base64; este repositório contém o visual transparente usado pelo cliente Java.

## Referência das POCs

- A cabeça foi baseada na textura [Miner Helmet #26723](https://minecraft-heads.com/custom-heads/head/26723-miner-helmet), adaptada para testar transparência em uma textura local do resource pack.
- A espada foi baseada numa referência de pixel art fornecida diretamente (lâmina verde com aresta clara e acentos vermelhos, cabo de madeira), reproduzida pixel a pixel.
