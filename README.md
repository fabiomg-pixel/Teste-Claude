# Visualizador de Expressão Gênica

> Este repositório também contém o **[Leitor de EPUB com companheiro de leitura](epub_reader/)**,
> em `epub_reader/` — um leitor de e-books cuja conversa com a LLM só conhece o
> livro até onde você leu.

Aplicação web interativa para visualização de dados de expressão gênica a partir de arquivos CSV com counts normalizados do DESeq2.

## Funcionalidades

- Upload de arquivos CSV com dados DESeq2 normalizados
- Seleção interativa de genes (individual ou em lote)
- Busca de genes por nome
- Múltiplos tipos de visualização:
  - Gráfico de Barras
  - Gráfico de Linha
  - Mapa de Calor (Heatmap)
  - Box Plot
- Download dos dados filtrados
- Interface responsiva e intuitiva

## Formato do Arquivo CSV

O arquivo CSV deve ter o seguinte formato:

```csv
Gene,Sample1,Sample2,Sample3,Sample4
GENE1,120.5,98.3,145.2,110.8
GENE2,45.2,52.1,48.9,51.3
GENE3,89.7,92.4,88.1,90.5
```

- **Primeira coluna**: Nomes dos genes
- **Colunas seguintes**: Valores de expressão para cada amostra (counts normalizados)

## Instalação

### Requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

### Passos

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd Teste-Claude
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

## Execução

1. Inicie o servidor Flask:
```bash
python app.py
```

2. Abra o navegador e acesse:
```
http://localhost:5000
```

## Como Usar

### 1. Upload do Arquivo

- Clique em "Escolher arquivo" e selecione seu arquivo CSV
- Clique em "Carregar Arquivo"
- Aguarde a confirmação de upload

### 2. Seleção de Genes

Você pode selecionar genes de três formas:

- **Individual**: Clique nos genes na lista
- **Busca**: Use a caixa de busca para filtrar genes
- **Lista em lote**: Clique em "Colar Lista" e cole uma lista de genes (um por linha)

Controles disponíveis:
- **Selecionar Todos**: Seleciona todos os genes visíveis
- **Limpar Seleção**: Remove todas as seleções

### 3. Visualização

1. Escolha o tipo de gráfico desejado:
   - **Gráfico de Barras**: Comparação entre amostras
   - **Gráfico de Linha**: Tendências ao longo das amostras
   - **Mapa de Calor**: Visão geral da expressão
   - **Box Plot**: Distribuição da expressão por gene

2. Clique em "Gerar Gráfico"

3. Interaja com o gráfico:
   - Zoom: Arraste sobre a área
   - Pan: Clique e arraste
   - Reset: Duplo clique
   - Download: Use o botão na barra de ferramentas

### 4. Download dos Dados

- Clique em "Baixar Dados" para exportar apenas os genes selecionados em formato CSV

## Estrutura do Projeto

```
Teste-Claude/
├── app.py                  # Backend Flask
├── requirements.txt        # Dependências Python
├── README.md              # Este arquivo
├── templates/
│   └── index.html         # Interface HTML
├── static/
│   ├── css/
│   │   └── style.css      # Estilos CSS
│   └── js/
│       └── app.js         # Lógica JavaScript
└── uploads/               # Diretório para arquivos temporários
```

## Tecnologias Utilizadas

- **Backend**: Flask (Python)
- **Processamento de Dados**: Pandas
- **Visualização**: Plotly
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)

## Limitações

- Tamanho máximo de arquivo: 16MB
- Os dados são armazenados em memória durante a sessão
- Para uso em produção, considere implementar:
  - Sistema de sessões persistentes
  - Banco de dados para armazenamento
  - Autenticação de usuários
  - Cache de resultados

## Solução de Problemas

### Erro ao carregar arquivo
- Verifique se o arquivo está no formato CSV
- Certifique-se de que a primeira coluna contém os nomes dos genes
- Verifique se não há linhas vazias ou caracteres especiais

### Genes não encontrados
- Verifique a grafia exata dos nomes dos genes
- Os nomes são case-sensitive (maiúsculas/minúsculas importam)
- Confira se os genes existem no arquivo carregado

### Gráfico não aparece
- Verifique se há genes selecionados
- Tente recarregar a página
- Verifique o console do navegador para erros JavaScript

## Contribuindo

Contribuições são bem-vindas! Por favor:

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

## Licença

Este projeto é disponibilizado sob a licença MIT.

## Contato

Para dúvidas ou sugestões, abra uma issue no repositório.
