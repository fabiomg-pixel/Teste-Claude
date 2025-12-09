let allGenes = [];
let filteredGenes = [];
let selectedGenes = new Set();

// Upload file
async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];

    if (!file) {
        showStatus('Por favor, selecione um arquivo.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    showStatus('Carregando arquivo...', 'success');

    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            allGenes = data.genes;
            filteredGenes = [...allGenes];
            showStatus(`Arquivo carregado com sucesso! ${data.total_genes} genes e ${data.total_samples} amostras encontrados.`, 'success');
            displayGenes();
            document.getElementById('geneSelectionSection').style.display = 'block';
        } else {
            showStatus(data.error || 'Erro ao carregar arquivo.', 'error');
        }
    } catch (error) {
        showStatus('Erro ao comunicar com o servidor: ' + error.message, 'error');
    }
}

// Display genes
function displayGenes() {
    const geneList = document.getElementById('geneList');
    geneList.innerHTML = '';

    filteredGenes.forEach(gene => {
        const geneItem = document.createElement('div');
        geneItem.className = 'gene-item';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `gene_${gene}`;
        checkbox.value = gene;
        checkbox.checked = selectedGenes.has(gene);
        checkbox.onchange = () => toggleGene(gene);

        const label = document.createElement('label');
        label.htmlFor = `gene_${gene}`;
        label.textContent = gene;
        label.onclick = () => {
            checkbox.checked = !checkbox.checked;
            toggleGene(gene);
        };

        geneItem.appendChild(checkbox);
        geneItem.appendChild(label);
        geneList.appendChild(geneItem);
    });

    updateSelectedCount();
}

// Toggle gene selection
function toggleGene(gene) {
    if (selectedGenes.has(gene)) {
        selectedGenes.delete(gene);
    } else {
        selectedGenes.add(gene);
    }
    updateSelectedCount();

    if (selectedGenes.size > 0) {
        document.getElementById('plotSection').style.display = 'block';
    }
}

// Update selected count
function updateSelectedCount() {
    document.getElementById('selectedCount').textContent = `${selectedGenes.size} genes selecionados`;
}

// Filter genes
function filterGenes() {
    const searchTerm = document.getElementById('geneSearch').value.toLowerCase();
    filteredGenes = allGenes.filter(gene => gene.toLowerCase().includes(searchTerm));
    displayGenes();
}

// Select all genes
function selectAll() {
    filteredGenes.forEach(gene => selectedGenes.add(gene));
    displayGenes();
    document.getElementById('plotSection').style.display = 'block';
}

// Deselect all genes
function deselectAll() {
    selectedGenes.clear();
    displayGenes();
}

// Show modal for pasting gene list
function selectFromList() {
    document.getElementById('geneListModal').style.display = 'block';
}

// Close modal
function closeModal() {
    document.getElementById('geneListModal').style.display = 'none';
    document.getElementById('geneListInput').value = '';
}

// Apply gene list from modal
function applyGeneList() {
    const input = document.getElementById('geneListInput').value;
    const genes = input.split('\n')
        .map(g => g.trim())
        .filter(g => g.length > 0);

    selectedGenes.clear();
    genes.forEach(gene => {
        if (allGenes.includes(gene)) {
            selectedGenes.add(gene);
        }
    });

    displayGenes();
    closeModal();

    if (selectedGenes.size > 0) {
        document.getElementById('plotSection').style.display = 'block';
        showStatus(`${selectedGenes.size} genes selecionados da lista.`, 'success');
    } else {
        showStatus('Nenhum gene da lista foi encontrado no arquivo.', 'error');
    }
}

// Generate plot
async function generatePlot() {
    if (selectedGenes.size === 0) {
        showStatus('Por favor, selecione pelo menos um gene.', 'error');
        return;
    }

    const plotType = document.getElementById('plotType').value;

    showStatus('Gerando gráfico...', 'success');

    try {
        const response = await fetch('/plot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                genes: Array.from(selectedGenes),
                plot_type: plotType
            })
        });

        const data = await response.json();

        if (data.success) {
            Plotly.newPlot('plotContainer', data.plot.data, data.plot.layout, {
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                displaylogo: false
            });
            showStatus('Gráfico gerado com sucesso!', 'success');
        } else {
            showStatus(data.error || 'Erro ao gerar gráfico.', 'error');
        }
    } catch (error) {
        showStatus('Erro ao comunicar com o servidor: ' + error.message, 'error');
    }
}

// Download filtered data
async function downloadData() {
    if (selectedGenes.size === 0) {
        showStatus('Por favor, selecione pelo menos um gene.', 'error');
        return;
    }

    try {
        const response = await fetch('/download_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                genes: Array.from(selectedGenes)
            })
        });

        const data = await response.json();

        if (data.success) {
            // Create blob and download
            const blob = new Blob([data.csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `gene_expression_filtered_${new Date().getTime()}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            showStatus('Dados baixados com sucesso!', 'success');
        } else {
            showStatus(data.error || 'Erro ao baixar dados.', 'error');
        }
    } catch (error) {
        showStatus('Erro ao comunicar com o servidor: ' + error.message, 'error');
    }
}

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;

    if (type === 'success') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 5000);
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('geneListModal');
    if (event.target === modal) {
        closeModal();
    }
}
