/**
 * Informe técnico TFG — dinámica de frente observada (CMA / material Heligrafics)
 * Genera DOCX A4. Ejecutar: node docs/entrega_cma/build_informe_cma.js
 */
const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  ImageRun,
  Header,
  Footer,
  AlignmentType,
  HeadingLevel,
  BorderStyle,
  WidthType,
  ShadingType,
  VerticalAlign,
  PageNumber,
  LevelFormat,
} = require("docx");

const ROOT = path.resolve(__dirname, "../..");
const OUT = path.join(__dirname, "Informe_tecnico_dinamica_frente_v1.0.docx");
const FIG_AREA = path.join(__dirname, "fig_tobarra_area.png");
const FIG_ROS = path.join(__dirname, "fig_tobarra_ros.png");

const PAGE_W = 11906; // A4
const PAGE_H = 16838;
const MARGIN = 850; // ~1.5 cm
const CONTENT_W = PAGE_W - 2 * MARGIN; // 10206

const thin = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const borders = { top: thin, bottom: thin, left: thin, right: thin };
const noBorder = {
  style: BorderStyle.NONE,
  size: 0,
  color: "FFFFFF",
};
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
const headerBorder = {
  top: noBorder,
  bottom: { style: BorderStyle.SINGLE, size: 12, color: "1F4E79" },
  left: noBorder,
  right: noBorder,
};

function cell(text, opts = {}) {
  const {
    bold = false,
    fill = null,
    width = 2551,
    align = AlignmentType.LEFT,
    fontSize = 18,
    color = "000000",
  } = opts;
  return new TableCell({
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 50, bottom: 50, left: 80, right: 80 },
    verticalAlign: VerticalAlign.CENTER,
    children: [
      new Paragraph({
        alignment: align,
        children: [
          new TextRun({
            text: String(text),
            bold,
            font: "Calibri",
            size: fontSize,
            color,
          }),
        ],
      }),
    ],
  });
}

function headerRow(cols, widths) {
  return new TableRow({
    children: cols.map((c, i) =>
      cell(c, {
        bold: true,
        fill: "1F4E79",
        width: widths[i],
        color: "FFFFFF",
        fontSize: 17,
        align: AlignmentType.CENTER,
      })
    ),
  });
}

function dataRow(cols, widths, alt = false) {
  return new TableRow({
    children: cols.map((c, i) =>
      cell(c, {
        width: widths[i],
        fill: alt ? "F2F2F2" : "FFFFFF",
        fontSize: 17,
        align: i === 0 ? AlignmentType.LEFT : AlignmentType.CENTER,
      })
    ),
  });
}

function p(text, opts = {}) {
  const { bold = false, size = 20, after = 120, before = 0, italics = false, color = "000000" } =
    opts;
  return new Paragraph({
    spacing: { after, before, line: 276 },
    children: [
      new TextRun({
        text,
        bold,
        italics,
        font: "Calibri",
        size,
        color,
      }),
    ],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 280, after: 140 },
    children: [new TextRun({ text, bold: true, font: "Calibri", size: 26, color: "1F4E79" })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 220, after: 100 },
    children: [new TextRun({ text, bold: true, font: "Calibri", size: 22, color: "2E75B6" })],
  });
}

function metaLine(label, value) {
  return new Paragraph({
    spacing: { after: 40 },
    children: [
      new TextRun({ text: label + ": ", bold: true, font: "Calibri", size: 18 }),
      new TextRun({ text: value, font: "Calibri", size: 18 }),
    ],
  });
}

function bullet(text, ref = "bullets") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Calibri", size: 20 })],
  });
}

function numItem(text, ref = "nums") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60 },
    children: [new TextRun({ text, font: "Calibri", size: 20 })],
  });
}

function img(file, w, h, caption) {
  const nodes = [];
  if (fs.existsSync(file)) {
    nodes.push(
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 120, after: 60 },
        children: [
          new ImageRun({
            type: "png",
            data: fs.readFileSync(file),
            transformation: { width: w, height: h },
            altText: { title: caption, description: caption, name: path.basename(file) },
          }),
        ],
      })
    );
  }
  nodes.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { after: 160 },
      children: [
        new TextRun({
          text: caption,
          italics: true,
          font: "Calibri",
          size: 16,
          color: "444444",
        }),
      ],
    })
  );
  return nodes;
}

const w5 = [2200, 1600, 1600, 2400, 2406]; // sum 10206
const w4 = [2800, 2200, 2200, 3006];
const w3 = [3402, 3402, 3402];
const w2 = [3600, 6606];

const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Calibri", size: 20 },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: "1F4E79" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 22, bold: true, font: "Calibri", color: "2E75B6" },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "nums",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "pipeline",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "limits",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "next",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              border: {
                bottom: { style: BorderStyle.SINGLE, size: 12, color: "1F4E79", space: 4 },
              },
              spacing: { after: 120 },
              children: [
                new TextRun({
                  text: "TFG — Dinámica de frente a partir de secuencias térmicas aéreas  |  CONFIDENCIAL · uso académico",
                  font: "Calibri",
                  size: 14,
                  color: "666666",
                }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              border: {
                top: { style: BorderStyle.SINGLE, size: 6, color: "CCCCCC", space: 6 },
              },
              spacing: { before: 80 },
              children: [
                new TextRun({
                  text: "Ref. WFD-INF-2026-07-v1.0  ·  Alonso Alvira Ballano  ·  p. ",
                  font: "Calibri",
                  size: 14,
                  color: "666666",
                }),
                new TextRun({
                  children: [PageNumber.CURRENT],
                  font: "Calibri",
                  size: 14,
                  color: "666666",
                }),
                new TextRun({
                  text: " / ",
                  font: "Calibri",
                  size: 14,
                  color: "666666",
                }),
                new TextRun({
                  children: [PageNumber.TOTAL_PAGES],
                  font: "Calibri",
                  size: 14,
                  color: "666666",
                }),
              ],
            }),
          ],
        }),
      },
      children: [
        // PORTADA / control documental
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 80 },
          children: [
            new TextRun({
              text: "INFORME TÉCNICO",
              bold: true,
              font: "Calibri",
              size: 32,
              color: "1F4E79",
            }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 40 },
          children: [
            new TextRun({
              text: "Estimación de velocidad de propagación del frente",
              font: "Calibri",
              size: 24,
              color: "333333",
            }),
          ],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [
            new TextRun({
              text: "a partir de pasadas térmicas georreferenciadas",
              font: "Calibri",
              size: 24,
              color: "333333",
            }),
          ],
        }),
        p(
          "Documento de trabajo para el equipo CMA (GEACAM). Material de origen: secuencias IR/LWIR y productos asociados facilitados para TFG. Uso estrictamente académico y confidencial. No constituye parte operativo ni documento de despacho.",
          { size: 18, italics: true, after: 200, color: "444444" }
        ),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: w2,
          rows: [
            new TableRow({
              children: [
                cell("Campo", { bold: true, fill: "D6E3F0", width: w2[0], fontSize: 17 }),
                cell("Valor", { bold: true, fill: "D6E3F0", width: w2[1], fontSize: 17 }),
              ],
            }),
            dataRow(["Referencia", "WFD-INF-2026-07-v1.0"], w2, false),
            dataRow(["Versión", "1.0"], w2, true),
            dataRow(["Fecha", "2026-07-15"], w2, false),
            dataRow(["Autor", "Alonso Alvira Ballano"], w2, true),
            dataRow(["Ámbito", "TFG · Ingeniería Informática"], w2, false),
            dataRow(["Destinatario", "Pablo Arroyo / equipo CMA (GEACAM)"], w2, true),
            dataRow(["Motor de cálculo", "front_dynamics_v1"], w2, false),
            dataRow(["Estado", "Borrador técnico para revisión"], w2, true),
          ],
        }),

        h1("1. Objeto"),
        p(
          "Resumir el procesamiento realizado sobre las secuencias térmicas facilitadas, exponer el método de estimación de velocidad de avance del frente (m/min), presentar resultados numéricos por incendio y delimitar con claridad qué se puede afirmar y qué queda fuera de alcance."
        ),
        p(
          "Este informe no describe un sistema de predicción táctica en tiempo real. Describe un pipeline de análisis post-proceso sobre pasadas ya capturadas."
        ),

        h1("2. Alcance y fuera de alcance"),
        h2("2.1 Incluido"),
        bullet("Ingesta de GeoTIFF LWIR/IR georreferenciados (reproyección UTM 30N cuando aplica)."),
        bullet("Generación de máscaras de zona caliente por pasada (umbral adaptativo / frente principal)."),
        bullet("Comparación temporal entre pasadas consecutivas."),
        bullet(
          "Estimación multi-método de ROS (rate of spread) en m/min: área isótropa, radio equivalente y rayos normales al contorno."
        ),
        bullet("Export de capa de frente (GeoJSON), serie temporal y métricas operativas."),
        bullet("Comparación con ancla de parte cuando existe (caso Tobarra)."),

        h2("2.2 Fuera de alcance (v1.0)"),
        bullet("Predicción del perímetro a 15 / 30 / 60 minutos validada para uso en emergencia."),
        bullet("Uso del KMZ de pasada como perímetro oficial del incendio."),
        bullet("Sustitución del parte INFOCAM/FIDIAS o de la valoración de mando."),
        bullet("Garantía de monotomía de área en máscara térmica (la máscara no es el perímetro cartográfico)."),

        h1("3. Datos de entrada"),
        p(
          "Fuente: selección de IF aportada por CMA (enlaces Dropbox, julio 2026), más material Tobarra ya documentado. El equipo CMA advirtió de saltos temporales (campaña con una cámara; periodos de vuelo discontinuos). Ese aviso se ha tenido en cuenta en la interpretación."
        ),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: w5,
          rows: [
            headerRow(["Incendio (id)", "Frames usados", "Δt mediano", "Grado", "Ancla parte"], w5),
            dataRow(["tobarra_20240802", "10", "≈ 188 s", "A", "Sí (Vp 7; 39 ha)"], w5, false),
            dataRow(["cardoso_2025", "8", "≈ 16 s", "B", "No"], w5, true),
            dataRow(["hellin_2024", "8", "≈ 11 s", "B", "No"], w5, false),
            dataRow(["la_estrella_acom1_2024", "8", "≈ 125 s", "B", "No"], w5, true),
            dataRow(["retuerta_2025", "8", "≈ 105 s", "B", "No"], w5, false),
          ],
        }),
        p(
          "Nota: el grado A/B/C es interno al pipeline (defendibilidad de la estimación), no una clasificación operativa de CMA.",
          { size: 17, italics: true, color: "555555", after: 160 }
        ),

        h1("4. Método"),
        h2("4.1 Pipeline"),
        numItem("Reproyección / alineación geográfica de la trama térmica.", "pipeline"),
        numItem("Segmentación de zona caliente y extracción del componente de frente principal.", "pipeline"),
        numItem(
          "Emparejamiento temporal de contornos entre pasadas t_i y t_{i+1} (Δt conocido por metadatos).",
          "pipeline"
        ),
        numItem(
          "Cálculo de ROS por varios estimadores independientes. Si no hay señal suficiente, el intervalo se marca como abstención (no se inventa velocidad).",
          "pipeline"
        ),
        numItem(
          "Fusión a una ROS primaria (mediana robusta sobre intervalos válidos) y asignación de grado de calidad.",
          "pipeline"
        ),

        h2("4.2 Estimadores de ROS"),
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: w3,
          rows: [
            headerRow(["Estimador", "Idea", "Uso típico"], w3),
            dataRow(
              ["area_isotropic", "dA / (P · dt)", "Expansión de área; robusto si el contorno es ruidoso"],
              w3,
              false
            ),
            dataRow(
              ["equiv_radius", "d√(A/π) / dt", "Crecimiento del radio equivalente"],
              w3,
              true
            ),
            dataRow(
              ["normal_ray", "Avance local normal al contorno", "Dirección de propagación local"],
              w3,
              false
            ),
          ],
        }),
        p(
          "Valores implausibles (p. ej. por saltos de máscara o Δt muy corto con cambio de silueta) se filtran. No se aplica factor de escala para forzar coincidencia con el parte: la comparación con ancla es a posteriori y se reporta en crudo.",
          { after: 160 }
        ),

        h2("4.3 Sobre el KMZ"),
        p(
          "El KMZ de Heligrafics sitúa la pasada o el producto de imagen. No se ha tratado como contorno del incendio. Para un error geométrico (Hausdorff / distancia media al perímetro) hace falta un croquis o capa de perímetro independiente, aunque sea de un solo instante."
        ),

        h1("5. Resultados"),
        h2("5.1 Caso de referencia: Tobarra (2024-08-02)"),
        p(
          "Secuencia con 10 observaciones. Intervalo mediano entre pasadas ≈ 3,1 min. Área por máscara térmica no monótona (máx. 51,9 ha; ancla de parte 39 ha): la máscara sobreestima o subestima según oclusión, umbral y geometría de vuelo; no se interpreta como superficie oficial."
        ),

        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: w2,
          rows: [
            new TableRow({
              children: [
                cell("Métrica", { bold: true, fill: "D6E3F0", width: w2[0], fontSize: 17 }),
                cell("Valor", { bold: true, fill: "D6E3F0", width: w2[1], fontSize: 17 }),
              ],
            }),
            dataRow(["ROS primaria (mediana)", "5,71 m/min"], w2, false),
            dataRow(["P25 – P75 (ROS primaria)", "2,78 – 6,90 m/min"], w2, true),
            dataRow(["Métodos que aportan señal", "area_isotropic, equiv_radius, normal_ray"], w2, false),
            dataRow(["Pares temporales analizados", "9"], w2, true),
            dataRow(["Ancla Vp (INFOCAM / parte)", "7,0 m/min"], w2, false),
            dataRow(["Ratio ROS / Vp ancla", "0,82"], w2, true),
            dataRow(["Interpretación", "Mismo orden de magnitud (grado A)"], w2, false),
            dataRow(["Área máx. máscara / ancla ha", "51,9 / 39,0 (ratio 1,33)"], w2, true),
            dataRow(["Coregistro residual medio", "0,0 m (no aplicado en esta corrida)"], w2, false),
          ],
        }),

        ...img(
          FIG_AREA,
          480,
          214,
          "Figura 1. Evolución del área de máscara térmica (proxy). Línea roja: 39 ha del parte."
        ),
        ...img(
          FIG_ROS,
          480,
          214,
          "Figura 2. ROS primaria en intervalos no abstinidos. Línea roja: Vp 7 m/min del parte."
        ),

        p(
          "Comentario técnico: hay intervalos con abstención (p. ej. cambios bruscos de silueta o IoU de emparejamiento bajo). Eso es intencional. Forzar una velocidad en esos tramos empeoraría la mediana sin ganar verosimilitud.",
          { after: 160 }
        ),

        h2("5.2 Resto de IF (sin ancla de parte)"),
        new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: w4,
          rows: [
            headerRow(["Incendio", "ROS prim. (m/min)", "Métodos", "Grado / nota"], w4),
            dataRow(["cardoso_2025", "30,2", "area_isotropic", "B — sin ancla; muestra corta"], w4, false),
            dataRow(["hellin_2024", "16,0", "area_isotropic", "B — sin ancla; muestra corta"], w4, true),
            dataRow(
              ["la_estrella_acom1_2024", "39,3", "area + normal", "B — señal parcial"],
              w4,
              false
            ),
            dataRow(
              ["retuerta_2025", "58,7", "area_isotropic", "B — área máscara anómala (revisar)"],
              w4,
              true
            ),
          ],
        }),
        p(
          "Estos valores son orientativos. Sin Vp o hectáreas de parte no se puede cerrar si el orden de magnitud es correcto. En Retuerta el área de máscara sale desproporcionada (posible FOV, umbral o fusión de componentes); no se reporta como superficie creíble del IF hasta revisión de la cadena de máscaras.",
          { after: 160 }
        ),

        h1("6. Limitaciones"),
        numItem(
          "Saltos temporales entre periodos de vuelo: el fuego puede evolucionar fuera de cámara; el estimador solo ve lo muestreado.",
          "limits"
        ),
        numItem(
          "Máscara térmica ≠ perímetro oficial. El área en ha es proxy de la silueta caliente, no del croquis de extinción.",
          "limits"
        ),
        numItem(
          "KMZ de pasada ≠ contorno del incendio. No se ha usado para validación geométrica del frente.",
          "limits"
        ),
        numItem(
          "ROS multi-estimador es orientación post-proceso, no sustituto de Vp de parte ni de decisión de mando.",
          "limits"
        ),
        numItem(
          "Modelos de aprendizaje (predicción a corto plazo) están en desarrollo con datos abiertos y con estas secuencias; no forman parte del producto validado de este informe.",
          "limits"
        ),

        h1("7. Productos generados por incendio"),
        bullet("operational_metrics.json — métricas y grado de calidad."),
        bullet("front_dynamics.json — detalle multi-estimador y pares temporales."),
        bullet("main_front.geojson / fronts.geojson — geometría del frente."),
        bullet("ros_timeline.csv — ROS por intervalo (incluye abstenciones)."),
        bullet("operational_report.html / brief_operativo.md — lectura rápida."),
        p(
          "Ruta de trabajo local (repositorio TFG): outputs/observatorio/<id_incendio>/",
          { size: 17, italics: true, color: "555555" }
        ),

        h1("8. Qué se necesita para el siguiente paso de validación"),
        p("Sin acceso a bases de datos internas. Con lo mínimo:"),
        numItem(
          "Tabla por IF (2–3 casos): Vp media o rango (m/min), ha de parte, fecha/hora aproximada del parte. Prioridad: Cardoso, Hellín, La Estrella.",
          "next"
        ),
        numItem(
          "Un croquis o perímetro vectorial de un solo incendio (SHP/GPKG/GeoJSON), aunque sea de un instante, para medir error geométrico del frente extraído.",
          "next"
        ),
        numItem(
          "Si está disponible: material adicional de Cardoso (secuencia larga), en el formato que ya se ha usado (varios enlaces).",
          "next"
        ),
        p(
          "Con (1) se puede pasar de un único caso grado A a validación multi-incendio. Con (2) se cierra la métrica de error en metros respecto a un contorno independiente."
        ),

        h1("9. Conclusiones"),
        numItem(
          "El pipeline es reproducible sobre las secuencias térmicas georreferenciadas facilitadas.",
          "nums"
        ),
        numItem(
          "En Tobarra, ROS primaria 5,71 m/min frente a Vp de parte 7 m/min (ratio 0,82): compatible en orden de magnitud; se reporta sin reescalar.",
          "nums"
        ),
        numItem(
          "En el resto de IF el cálculo es posible pero no validado operativamente hasta disponer de anclas de parte.",
          "nums"
        ),
        numItem(
          "El KMZ de pasada no sustituye un perímetro de incendio para evaluación geométrica.",
          "nums"
        ),
        numItem(
          "La predicción ML a horizontes cortos no se presenta como producto operativo en esta versión.",
          "nums"
        ),

        h1("10. Contacto"),
        metaLine("Autor", "Alonso Alvira Ballano"),
        metaLine("Correo", "alonso.alvbal@gmail.com"),
        metaLine("Documento", "WFD-INF-2026-07-v1.0"),
        p(
          "Cualquier corrección de nomenclatura de IF, fechas de parte o criterios de CMA se incorporará en v1.1.",
          { before: 120, size: true, size: 18, color: "555555" }
        ),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log("Wrote", OUT);
});
