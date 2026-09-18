# IcarusTexture

Resource pack do IcarusRPG para **Minecraft Java 26.2**.

A **Miner's Armor** usa as quatro peças de couro como itens-base, com ícones próprios e um equipment asset compartilhado. O conjunto combina capacete marrom com lâmpada, jaqueta azul-grafite, arnês e cinto de couro, reforços metálicos e botas escuras. O rosto e a skin do jogador permanecem visíveis sob o capacete.

A **Undead's Sword** usa um item model customizado (16×16) aplicado pelo IcarusRPG via componente `minecraft:item_model`.

## Estrutura

```text
IcarusTexture/
├── pack.mcmeta
└── assets/
    └── icarus/
        ├── equipment/
        │   └── miner_helmet.json
        ├── textures/
        │   ├── entity/equipment/humanoid/
        │   │   └── miner_helmet.png
        │   ├── heads/
        │   │   └── miner_helmet.png
        │   └── item/
        │       ├── miner_helmet.png
        │       └── undead_sword.png
        ├── items/
        │   ├── miner_helmet.json
        │   └── undead_sword.json
        └── models/
            └── item/
                ├── miner_helmet.json
                └── undead_sword.json
```

O identificador do equipment asset do conjunto é:

```text
icarus:miner_armor
icarus:menu_background
```

O identificador do item model da espada é:

```text
icarus:undead_sword
```

## Teste no jogo

Instale o repositório como resource pack ou compacte o conteúdo da raiz em um arquivo ZIP. Ative o pack no Minecraft Java 26.2 e execute:

```mcfunction
/give @s minecraft:leather_helmet[minecraft:item_model="icarus:miner_helmet",minecraft:equippable={slot:"head",asset_id:"icarus:miner_helmet"}]
/give @s minecraft:iron_sword[minecraft:item_model="icarus:undead_sword"]
```

Teste a cabeça no inventário, na mão, colocada no mundo e equipada pelo jogador. Teste a espada no inventário e na mão.

## Escopo atual

- Minecraft Java 26.2 (`pack_format` 88)
- namespace `icarus`
- textura equipada do capacete em PNG 64×32, ícone em PNG 16×16 e textura da espada em PNG 16×16, todos com canal alpha
- arquivos-fonte e releases prontas para uso obrigatório pelo servidor

No Bedrock/Geyser, o item-base continua sendo um capacete de couro até que exista um pack Bedrock e um mapeamento próprios; ele não depende mais de perfil Base64.

## Referência das POCs

- A cabeça foi baseada na textura [Miner Helmet #26723](https://minecraft-heads.com/custom-heads/head/26723-miner-helmet), adaptada para testar transparência em uma textura local do resource pack.
- A espada foi baseada numa referência de pixel art fornecida diretamente (lâmina verde com aresta clara e acentos vermelhos, cabo de madeira), reproduzida pixel a pixel.
