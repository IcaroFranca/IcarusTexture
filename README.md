# IcarusTexture

Resource pack experimental para **Minecraft Java 26.2**.

Este primeiro commit contém a prova de conceito V2 do **Miner Helmet**, uma textura de `player_head` que usa transparência real para remover o preenchimento cinza/azulado da cabeça sem apagar as tiras e os detalhes do capacete.

Um segundo asset adiciona o **item model** da **Undead's Sword**, um item customizado (16×16) usado pelo IcarusRPG via componente `minecraft:item_model`.

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

Teste a cabeça no inventário, na mão, colocada no mundo e equipada pelo jogador. Teste a espada no inventário e na mão. Essas texturas ainda são provas de conceito e podem receber ajustes após a validação visual no jogo.

## Escopo atual

- Minecraft Java 26.2 (`pack_format` 88)
- namespace `icarus`
- textura V2 da cabeça em PNG 64×64 com canal alpha; textura da espada em PNG 16×16 com canal alpha
- somente arquivos-fonte do resource pack

Ainda não há versão Bedrock/Geyser nem pacote de release neste repositório.

## Referência das POCs

- A cabeça foi baseada na textura [Miner Helmet #26723](https://minecraft-heads.com/custom-heads/head/26723-miner-helmet), adaptada para testar transparência em uma textura local do resource pack.
- A espada foi baseada numa referência de pixel art fornecida diretamente (lâmina verde com aresta clara e acentos vermelhos, cabo de madeira), reproduzida pixel a pixel.
