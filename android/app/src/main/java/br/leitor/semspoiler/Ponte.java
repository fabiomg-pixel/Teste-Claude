package br.leitor.semspoiler;

import android.content.Context;
import android.content.SharedPreferences;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * A ponte entre a página e a API da Anthropic.
 *
 * A chamada acontece aqui, em Java, por dois motivos: a chave não precisa
 * transitar pelo JavaScript da página, e não há CORS a contornar. A página
 * manda o pedido já montado — inclusive o recorte anti-spoiler — e recebe a
 * resposta em pedaços.
 */
public class Ponte {

    private static final String ENDERECO = "https://api.anthropic.com/v1/messages";
    private static final String VERSAO_API = "2023-06-01";
    private static final String MODELO_PADRAO = "claude-opus-5";
    private static final int MAX_TOKENS = 8000;

    private final MainActivity tela;
    private final WebView web;
    private final SharedPreferences cofre;
    private final ExecutorService fila = Executors.newSingleThreadExecutor();
    private final Set<String> cancelados = Collections.newSetFromMap(new ConcurrentHashMap<>());

    Ponte(MainActivity tela, WebView web) {
        this.tela = tela;
        this.web = web;
        this.cofre = tela.getSharedPreferences("leitor", Context.MODE_PRIVATE);
    }

    // ------------------------------------------------------------ chave

    @JavascriptInterface
    public boolean temChave() {
        String chave = cofre.getString("chave", "");
        return chave != null && chave.length() > 10;
    }

    @JavascriptInterface
    public void salvarChave(String chave) {
        cofre.edit().putString("chave", chave == null ? "" : chave.trim()).apply();
    }

    @JavascriptInterface
    public void apagarChave() {
        cofre.edit().remove("chave").apply();
    }

    @JavascriptInterface
    public String modelo() {
        return cofre.getString("modelo", MODELO_PADRAO);
    }

    @JavascriptInterface
    public void salvarModelo(String modelo) {
        if (modelo != null && !modelo.isEmpty()) cofre.edit().putString("modelo", modelo).apply();
    }

    @JavascriptInterface
    public void corDaBarra(String hex) {
        if (hex != null && !hex.trim().isEmpty()) tela.aplicarCorDaBarra(hex);
    }

    // --------------------------------------------------------- pergunta

    @JavascriptInterface
    public void cancelar(String id) {
        if (id != null) cancelados.add(id);
    }

    @JavascriptInterface
    public void perguntar(final String id, final String sistema, final String mensagensJson) {
        final String chave = cofre.getString("chave", "");
        final String modelo = modelo();
        if (chave == null || chave.length() < 10) {
            paraPagina("erro", id, "Nenhuma chave guardada neste aparelho.");
            return;
        }
        fila.execute(() -> conversar(id, chave, modelo, sistema, mensagensJson));
    }

    private void conversar(String id, String chave, String modelo, String sistema, String mensagensJson) {
        HttpURLConnection conexao = null;
        try {
            JSONObject corpo = new JSONObject();
            corpo.put("model", modelo);
            corpo.put("max_tokens", MAX_TOKENS);
            corpo.put("stream", true);
            corpo.put("system", sistema);
            corpo.put("messages", new JSONArray(mensagensJson));
            corpo.put("thinking", new JSONObject().put("type", "adaptive"));
            corpo.put("output_config", new JSONObject().put("effort", "medium"));

            conexao = (HttpURLConnection) new URL(ENDERECO).openConnection();
            conexao.setRequestMethod("POST");
            conexao.setDoOutput(true);
            conexao.setConnectTimeout(20000);
            conexao.setReadTimeout(180000);
            conexao.setRequestProperty("content-type", "application/json");
            conexao.setRequestProperty("accept", "text/event-stream");
            conexao.setRequestProperty("anthropic-version", VERSAO_API);
            conexao.setRequestProperty("x-api-key", chave);

            byte[] bytes = corpo.toString().getBytes(StandardCharsets.UTF_8);
            try (OutputStream saida = conexao.getOutputStream()) {
                saida.write(bytes);
            }

            int situacao = conexao.getResponseCode();
            if (situacao != 200) {
                paraPagina("erro", id, descreverFalha(situacao, conexao.getErrorStream()));
                return;
            }

            try (BufferedReader leitor = new BufferedReader(
                    new InputStreamReader(conexao.getInputStream(), StandardCharsets.UTF_8))) {
                String linha;
                while ((linha = leitor.readLine()) != null) {
                    if (cancelados.remove(id)) return;
                    if (!linha.startsWith("data:")) continue;
                    String bruto = linha.substring(5).trim();
                    if (bruto.isEmpty() || "[DONE]".equals(bruto)) continue;

                    JSONObject evento = new JSONObject(bruto);
                    String tipo = evento.optString("type");

                    if ("content_block_delta".equals(tipo)) {
                        JSONObject pedaco = evento.optJSONObject("delta");
                        if (pedaco != null && "text_delta".equals(pedaco.optString("type"))) {
                            String texto = pedaco.optString("text", "");
                            if (!texto.isEmpty()) paraPagina("delta", id, texto);
                        }
                    } else if ("message_delta".equals(tipo)) {
                        JSONObject fim = evento.optJSONObject("delta");
                        if (fim != null && "refusal".equals(fim.optString("stop_reason"))) {
                            paraPagina("erro", id, "O modelo recusou responder a esta mensagem.");
                            return;
                        }
                    } else if ("error".equals(tipo)) {
                        JSONObject falha = evento.optJSONObject("error");
                        paraPagina("erro", id, falha == null ? "Erro na resposta."
                                : falha.optString("message", "Erro na resposta."));
                        return;
                    }
                }
            }
            paraPagina("fim", id, null);
        } catch (java.net.SocketTimeoutException espera) {
            paraPagina("erro", id, "A resposta demorou demais. Tente de novo.");
        } catch (java.net.UnknownHostException semRede) {
            paraPagina("erro", id, "Sem conexão com a internet.");
        } catch (Exception erro) {
            String detalhe = erro.getMessage() == null ? erro.getClass().getSimpleName() : erro.getMessage();
            paraPagina("erro", id, "Falha ao falar com a API: " + detalhe);
        } finally {
            cancelados.remove(id);
            if (conexao != null) conexao.disconnect();
        }
    }

    private String descreverFalha(int situacao, InputStream fluxoDeErro) {
        String mensagem = "";
        if (fluxoDeErro != null) {
            try (BufferedReader leitor = new BufferedReader(
                    new InputStreamReader(fluxoDeErro, StandardCharsets.UTF_8))) {
                StringBuilder acumulado = new StringBuilder();
                String linha;
                while ((linha = leitor.readLine()) != null) acumulado.append(linha);
                JSONObject resposta = new JSONObject(acumulado.toString());
                JSONObject erro = resposta.optJSONObject("error");
                if (erro != null) mensagem = erro.optString("message", "");
            } catch (Exception ignorado) {
                // corpo de erro ilegível: fica só o código
            }
        }
        switch (situacao) {
            case 401:
                return "A chave não foi aceita (401). Confira se ela está correta e ativa.";
            case 403:
                return "A chave não tem permissão para este modelo (403).";
            case 429:
                return "Limite de uso atingido (429). Espere um pouco e tente de novo.";
            case 400:
                return mensagem.isEmpty() ? "Pedido inválido (400)." : "Pedido inválido: " + mensagem;
            default:
                if (situacao >= 500) return "A API está com problema (" + situacao + "). Tente mais tarde.";
                return mensagem.isEmpty() ? ("Erro " + situacao + ".") : mensagem;
        }
    }

    private void paraPagina(String funcao, String id, String argumento) {
        final String js = argumento == null
                ? "window.__ponte." + funcao + "(" + JSONObject.quote(id) + ")"
                : "window.__ponte." + funcao + "(" + JSONObject.quote(id) + ","
                  + JSONObject.quote(argumento) + ")";
        web.post(() -> web.evaluateJavascript(js, null));
    }

    void encerrar() {
        fila.shutdownNow();
    }
}
