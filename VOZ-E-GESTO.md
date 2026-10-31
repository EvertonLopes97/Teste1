# VOZ, GESTO E A FOTO DA THUMB — o que só você pode fazer

Três coisas que o sistema **não** consegue resolver sozinho, porque dependem de gravação sua.
Feitas uma vez, valem para todos os canais (notícias, GTA 6, histórias e shop).

---

## 1. VOZ — da melhor para a pior

O sistema tenta nesta ordem e para na primeira que funcionar:

| | Voz | Como é | O que falta |
|---|---|---|---|
| 1 | **VoiceStudio** (a SUA voz clonada) | é você | abrir o app com a sua voz cadastrada |
| 2 | **Fish Audio** | clonada, sotaque BR | a chave está sendo recusada (erro 403) |
| 3 | **Neural pt-BR** (Microsoft) | natural, mas não é você | nada — já funciona |
| 4 | Chatterbox | sotaque de Portugal, horas de render | último recurso, quase nunca entra |

### Para sair na SUA voz (o que resolve de vez)

1. Abra o **VoiceStudio** no PC.
2. Cadastre a sua voz com **30 a 60 segundos** de áudio seu. Como gravar:
   - lugar silencioso, sem música, sem ventilador, sem TV;
   - celular a um palmo da boca;
   - leia um texto qualquer no seu ritmo normal de vídeo — nem lendo devagar, nem acelerado;
   - **não** grite e **não** sussurre: a clonagem copia o jeito, inclusive o exagero.
3. No nome do perfil ponha **everton**, **detto** ou **minha voz** — o sistema procura por esses nomes.
4. **Deixe o VoiceStudio aberto.** Fechado, ele não responde e a rodada cai para a próxima voz.
5. No painel, aba **CANAIS**: confere se está ligado, escolhe a voz e a velocidade.

Conferir a qualquer momento: `python tools\doutor.py` → a seção **VOZ** diz se ele está aberto, quantas vozes
tem cadastradas e qual voz vai sair.

### Se quiser consertar o Fish (opcional)

A chave atual está sendo recusada (403 = expirou, acabou o crédito ou está errada). Gere outra em fish.audio e:

```powershell
setx FISH_API_KEY "a-chave-nova"
```

Feche e abra o PowerShell depois. **Nunca cole chave aqui no chat.**

### Ajustar a voz neural (enquanto o VoiceStudio não estiver aberto)

```powershell
setx DETTO_VOZ_EDGE "pt-BR-AntonioNeural"        # masculina (padrão)
setx DETTO_VOZ_EDGE "pt-BR-FranciscaNeural"      # feminina
setx DETTO_VOZ_EDGE "pt-BR-ThalitaMultilingualNeural"
setx DETTO_PAUSA_NEURAL "0.30"   # pausa mínima entre frases; MAIOR = mais calmo, MENOR = atropelado
setx DETTO_PITCH_NEURAL "+2Hz"   # tom; +4Hz fica mais animado, -2Hz mais grave
```

> **Por que ela soava robótica**: não era a voz. O sistema cortava **toda** pausa dela para 0,13 s — regra feita
> para o Chatterbox, que deixa ar morto. A voz neural já respira certo e, atropelada, virava robô. Corrigido em
> 30/10: a pausa dela agora é 0,30 s.

---

## 2. GESTO — as gravações de máscara

São os vídeos seus que aparecem no canto enquanto a imprensa fala. Sem eles o canal não roda.

**Onde subir:** `Meu Drive\DETTO\canal_noticias\mascara`
(o sistema copia sozinho a cada rodada; o canal de GTA usa a mesma pasta)

**O que gravar — 6 a 10 clipes, de 8 a 15 segundos cada:**

| Nome do arquivo | O que fazer na câmera |
|---|---|
| `ouvindo.mp4` | só escutando, acenando de leve a cabeça — **é o mais usado** (entra enquanto a imprensa fala) |
| `calmo.mp4` | parado, olhando para a câmera, expressão neutra |
| `animado.mp4` | empolgado, gesticulando |
| `surpreso.mp4` | cara de "não acredito" |
| `bravo.mp4` | indignado, reclamando |
| `rindo.mp4` | rindo |
| `comemorando.mp4` | comemorando |

Grave **2 ou 3 do "ouvindo"** (ouvindo1, ouvindo2...). É esse que mais repete.

**Como gravar:**
- mesma roupa, mesma luz e mesmo fundo em todos — eles se alternam dentro do mesmo vídeo;
- olhe para a câmera;
- **não fale** (o áudio da máscara não é usado);
- comece e termine o gesto dentro do clipe, sem travar no meio;
- pode deixar o dedo indo no botão de gravar: o sistema corta as pontas sozinho.

**Por que o gesto parecia robô:** uma gravação de 6 s num trecho de 90 s dava 15 voltas do mesmo movimento.
Desde 30/10 o sistema **emenda gravações diferentes** até cobrir o trecho — mas isso só funciona se existirem
várias. Com 1 clipe só, ele repete do mesmo jeito. **Mais clipes = menos robô.**

---

## 3. A FOTO DA THUMB

É o seu rosto recortado no canto da capa. Sem ela a thumb sai só com texto — e é justamente o rosto que faz
a thumb dos canais grandes funcionar.

**Onde pôr (qualquer um destes serve):**

| Onde | Para quê |
|---|---|
| `E:\DETTO\marca\eu.jpg` | a foto padrão — **comece por esta** |
| `E:\DETTO\thumb_rosto\*.jpg` | várias fotos; o sistema varia entre elas |
| `setx DETTO_FOTO "C:\caminho\foto.jpg"` | apontar para outro lugar |

**Como tem que ser a foto:**
- **um rosto só** na imagem (o recorte procura uma pessoa);
- olhando para a câmera;
- do **peito para cima** (é assim que entra na thumb);
- luz boa no rosto, fundo que contraste com você;
- **expressão forte** — surpreso, indignado, rindo. Foto séria de documento não funciona em thumb;
- de frente, nada de perfil; sem boné cobrindo os olhos.

Dica: tire 3 ou 4 com expressões diferentes e ponha todas em `thumb_rosto\`. Aí cada vídeo sai com uma cara.

Quando o vídeo é gravado por você (edição com roteiro, react), o sistema **não** precisa dessa foto: ele tira o
rosto da própria gravação, escolhendo o melhor quadro em que você olha para a câmera.

---

## Conferir se está tudo no lugar

```powershell
cd C:\Users\guebe\Teste1\detto-premiere-bridge
python tools\doutor.py
```

Abra `tools\diagnostico.txt`: a seção **VOZ** diz qual voz vai sair, e o painel (aba CANAIS) mostra se a
máscara e a voz de referência chegaram do Drive.
