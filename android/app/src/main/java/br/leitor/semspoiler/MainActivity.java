package br.leitor.semspoiler;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.webkit.WebViewAssetLoader;

/**
 * O app é uma casca: o leitor inteiro é a mesma página HTML publicada na web.
 * O que a casca acrescenta é o que o navegador não deixa fazer — falar com a
 * API da Anthropic com a sua chave, guardada aqui no aparelho.
 */
public class MainActivity extends Activity {

    private static final int PEDIDO_ARQUIVO = 7001;

    private WebView web;
    private Ponte ponte;
    private ValueCallback<Uri[]> escolhaDeArquivo;

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);

        web = new WebView(this);
        setContentView(web);

        WebSettings ajustes = web.getSettings();
        ajustes.setJavaScriptEnabled(true);
        ajustes.setDomStorageEnabled(true);
        ajustes.setDatabaseEnabled(true);
        ajustes.setAllowFileAccess(false);
        ajustes.setAllowContentAccess(false);
        ajustes.setMediaPlaybackRequiresUserGesture(true);
        ajustes.setSupportZoom(false);
        ajustes.setBuiltInZoomControls(false);
        // o leitor tem seu próprio controle de corpo do texto
        ajustes.setTextZoom(100);

        // Os assets são servidos por https://appassets.androidplatform.net —
        // origem segura, sem a qual o IndexedDB (a estante) não funcionaria.
        final WebViewAssetLoader carregador = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest pedido) {
                return carregador.shouldInterceptRequest(pedido.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest pedido) {
                Uri destino = pedido.getUrl();
                if ("appassets.androidplatform.net".equals(destino.getHost())) return false;
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, destino));
                } catch (ActivityNotFoundException ignorado) {
                    // sem navegador para abrir o link: não há o que fazer
                }
                return true;
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> retorno,
                                             FileChooserParams parametros) {
                if (escolhaDeArquivo != null) escolhaDeArquivo.onReceiveValue(null);
                escolhaDeArquivo = retorno;
                Intent escolha = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                escolha.addCategory(Intent.CATEGORY_OPENABLE);
                escolha.setType("*/*");
                escolha.putExtra(Intent.EXTRA_MIME_TYPES,
                        new String[]{"application/epub+zip", "application/x-mobipocket-ebook",
                                     "application/octet-stream"});
                try {
                    startActivityForResult(Intent.createChooser(escolha, "Escolha um EPUB"),
                            PEDIDO_ARQUIVO);
                } catch (ActivityNotFoundException erro) {
                    escolhaDeArquivo = null;
                    return false;
                }
                return true;
            }
        });

        ponte = new Ponte(this, web);
        web.addJavascriptInterface(ponte, "Ponte");

        if (estado != null) web.restoreState(estado);
        else web.loadUrl("https://appassets.androidplatform.net/assets/leitor.html");
    }

    @Override
    protected void onActivityResult(int pedido, int resultado, Intent dados) {
        if (pedido == PEDIDO_ARQUIVO) {
            if (escolhaDeArquivo == null) return;
            escolhaDeArquivo.onReceiveValue(
                    WebChromeClient.FileChooserParams.parseResult(resultado, dados));
            escolhaDeArquivo = null;
            return;
        }
        super.onActivityResult(pedido, resultado, dados);
    }

    /** O botão de voltar fecha primeiro o que estiver aberto dentro da página. */
    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        web.evaluateJavascript(
                "(window.__voltarNativo && window.__voltarNativo()) ? 'sim' : 'nao'",
                resposta -> {
                    if (resposta == null || !resposta.contains("sim")) finish();
                });
    }

    @Override
    protected void onSaveInstanceState(Bundle estado) {
        super.onSaveInstanceState(estado);
        web.saveState(estado);
    }

    @Override
    protected void onPause() {
        super.onPause();
        web.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (ponte != null) ponte.encerrar();
        super.onDestroy();
    }

    /** Pinta a barra de status com a cor do papel escolhido no leitor. */
    void aplicarCorDaBarra(String hex) {
        try {
            final int cor = Color.parseColor(hex.trim());
            runOnUiThread(() -> {
                Window janela = getWindow();
                janela.setStatusBarColor(cor);
                janela.setNavigationBarColor(cor);
                double luz = (0.299 * Color.red(cor) + 0.587 * Color.green(cor)
                        + 0.114 * Color.blue(cor)) / 255.0;
                View raiz = janela.getDecorView();
                int marcas = raiz.getSystemUiVisibility();
                if (luz > 0.6) marcas |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                else marcas &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    if (luz > 0.6) marcas |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                    else marcas &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
                }
                raiz.setSystemUiVisibility(marcas);
            });
        } catch (IllegalArgumentException corInvalida) {
            // cor que não dá para interpretar: fica a do tema
        }
    }
}
