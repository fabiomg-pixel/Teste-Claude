from flask import Flask, render_template, request, jsonify
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Store the current dataframe in memory (in production, use Redis or database)
current_data = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    if file and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            # Read CSV file
            df = pd.read_csv(filepath)

            # Store in memory
            current_data['df'] = df
            current_data['filepath'] = filepath

            # Get list of genes (assuming first column is gene names)
            gene_column = df.columns[0]
            genes = df[gene_column].tolist()

            # Get sample names (all columns except the first one)
            samples = df.columns[1:].tolist()

            return jsonify({
                'success': True,
                'genes': genes,
                'samples': samples,
                'total_genes': len(genes),
                'total_samples': len(samples)
            })

        except Exception as e:
            return jsonify({'error': f'Erro ao processar arquivo: {str(e)}'}), 400

    return jsonify({'error': 'Formato de arquivo inválido. Use apenas CSV.'}), 400

@app.route('/plot', methods=['POST'])
def generate_plot():
    data = request.json
    selected_genes = data.get('genes', [])
    plot_type = data.get('plot_type', 'bar')

    if 'df' not in current_data:
        return jsonify({'error': 'Nenhum arquivo carregado'}), 400

    if not selected_genes:
        return jsonify({'error': 'Nenhum gene selecionado'}), 400

    df = current_data['df']
    gene_column = df.columns[0]

    # Filter dataframe for selected genes
    filtered_df = df[df[gene_column].isin(selected_genes)]

    if filtered_df.empty:
        return jsonify({'error': 'Genes não encontrados no arquivo'}), 404

    # Prepare data for plotting
    plot_data = []

    for _, row in filtered_df.iterrows():
        gene_name = row[gene_column]
        for sample in df.columns[1:]:
            plot_data.append({
                'Gene': gene_name,
                'Sample': sample,
                'Expression': row[sample]
            })

    plot_df = pd.DataFrame(plot_data)

    # Generate plot based on type
    if plot_type == 'bar':
        fig = px.bar(
            plot_df,
            x='Sample',
            y='Expression',
            color='Gene',
            barmode='group',
            title='Expressão Gênica - Gráfico de Barras',
            labels={'Expression': 'Counts Normalizados', 'Sample': 'Amostras'}
        )
    elif plot_type == 'line':
        fig = px.line(
            plot_df,
            x='Sample',
            y='Expression',
            color='Gene',
            markers=True,
            title='Expressão Gênica - Gráfico de Linha',
            labels={'Expression': 'Counts Normalizados', 'Sample': 'Amostras'}
        )
    elif plot_type == 'heatmap':
        # Pivot data for heatmap
        pivot_df = plot_df.pivot(index='Gene', columns='Sample', values='Expression')
        fig = px.imshow(
            pivot_df,
            labels=dict(x='Amostras', y='Genes', color='Counts'),
            title='Expressão Gênica - Mapa de Calor',
            aspect='auto',
            color_continuous_scale='Viridis'
        )
    elif plot_type == 'box':
        fig = px.box(
            plot_df,
            x='Gene',
            y='Expression',
            color='Gene',
            title='Expressão Gênica - Box Plot',
            labels={'Expression': 'Counts Normalizados', 'Gene': 'Genes'}
        )
    else:
        fig = px.bar(plot_df, x='Sample', y='Expression', color='Gene', barmode='group')

    # Update layout for better visualization
    fig.update_layout(
        height=600,
        xaxis_tickangle=-45,
        hovermode='closest',
        template='plotly_white'
    )

    # Convert to JSON
    plot_json = fig.to_json()

    return jsonify({
        'success': True,
        'plot': json.loads(plot_json)
    })

@app.route('/download_data', methods=['POST'])
def download_data():
    data = request.json
    selected_genes = data.get('genes', [])

    if 'df' not in current_data:
        return jsonify({'error': 'Nenhum arquivo carregado'}), 400

    df = current_data['df']
    gene_column = df.columns[0]

    # Filter dataframe for selected genes
    filtered_df = df[df[gene_column].isin(selected_genes)]

    # Convert to CSV string
    csv_data = filtered_df.to_csv(index=False)

    return jsonify({
        'success': True,
        'csv': csv_data
    })

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
