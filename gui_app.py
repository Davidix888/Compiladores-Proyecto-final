from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, ttk

from compiler_core import CompilerError, generate_assembler, generate_c_code, parse_source


BLOCK_STYLES = {
    "inicio": {"label": "Inicio", "fill": "#e8ffe9", "outline": "#2c7a3f", "shape": "oval"},
    "proceso": {"label": "Proceso", "fill": "#e8f2ff", "outline": "#2a5caa", "shape": "rect"},
    "salida": {"label": "Salida", "fill": "#fff6d9", "outline": "#9b6c00", "shape": "para"},
    "decision": {"label": "Decision", "fill": "#ffecc7", "outline": "#9b6c00", "shape": "diamond"},
    "finsi": {"label": "FinSi", "fill": "#f7efff", "outline": "#6d4da3", "shape": "rect"},
    "fin": {"label": "Fin", "fill": "#e8ffe9", "outline": "#2c7a3f", "shape": "oval"},
}


DEFAULT_CONTENT = {
    "inicio": "",
    "proceso": "a = 0",
    "salida": "a",
    "decision": "a > 0",
    "finsi": "",
    "fin": "",
}


@dataclass(slots=True)
class FlowBlock:
    block_id: int
    block_type: str
    x: float
    y: float
    content: str


class CompilerGUI:
    BLOCK_WIDTH = 240
    BLOCK_HEIGHT = 62

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Editor de diagrama a C")
        self.root.geometry("1500x900")
        self.root.minsize(1180, 720)

        self.blocks: list[FlowBlock] = []
        self.next_block_id = 1
        self.selected_block_id: int | None = None
        self.dragging_palette_type: str | None = None
        self.dragging_block_id: int | None = None
        self.drag_offset_x = 0.0
        self.drag_offset_y = 0.0

        self.status_var = tk.StringVar(
            value="Arrastra un bloque desde el menu izquierdo al lienzo."
        )
        self.selected_type_var = tk.StringVar(value="Sin seleccion")
        self.content_var = tk.StringVar(value="")

        self._build_layout()
        self._load_example()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.columnconfigure(2, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=12)
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew")
        toolbar.columnconfigure(5, weight=1)

        ttk.Button(toolbar, text="Generar codigo", command=self.generate_from_diagram).grid(
            row=0, column=0, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Cargar ejemplo", command=self._load_example).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Eliminar bloque", command=self._delete_selected_block).grid(
            row=0, column=2, padx=(0, 8)
        )
        ttk.Button(toolbar, text="Limpiar", command=self._clear_all).grid(
            row=0, column=3, padx=(0, 8)
        )
        ttk.Label(toolbar, textvariable=self.status_var, foreground="#1f4d2e").grid(
            row=0, column=5, sticky="e"
        )

        palette_frame = ttk.LabelFrame(self.root, text="Menu de formas", padding=10)
        palette_frame.grid(row=1, column=0, sticky="ns", padx=(12, 6), pady=(0, 12))
        palette_frame.columnconfigure(0, weight=1)

        ttk.Label(
            palette_frame,
            text="Arrastra una forma al lienzo",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        row = 1
        for block_type in ("inicio", "proceso", "salida", "decision", "finsi", "fin"):
            label = ttk.Label(
                palette_frame,
                text=BLOCK_STYLES[block_type]["label"],
                relief="raised",
                padding=(12, 10),
                anchor="center",
                width=18,
            )
            label.grid(row=row, column=0, sticky="ew", pady=5)
            label.bind(
                "<ButtonPress-1>",
                lambda event, current=block_type: self._start_palette_drag(event, current),
            )
            row += 1

        hint = (
            "Proceso: ejemplo 'a = b + 1'\n"
            "Salida: ejemplo 'a + b'\n"
            "Decision: ejemplo 'a > 10'\n"
            "FinSi: cierra un bloque de decision"
        )
        ttk.Label(palette_frame, text=hint, justify="left", wraplength=220).grid(
            row=row, column=0, sticky="ew", pady=(12, 0)
        )

        canvas_frame = ttk.LabelFrame(self.root, text="Diagrama de flujo", padding=10)
        canvas_frame.grid(row=1, column=1, sticky="nsew", padx=6, pady=(0, 12))
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.flow_canvas = tk.Canvas(
            canvas_frame,
            background="#fffdf8",
            highlightthickness=0,
            width=640,
        )
        self.flow_canvas.grid(row=0, column=0, sticky="nsew")
        flow_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.flow_canvas.yview)
        flow_scroll.grid(row=0, column=1, sticky="ns")
        self.flow_canvas.configure(yscrollcommand=flow_scroll.set)
        self.flow_canvas.bind("<Button-1>", self._handle_canvas_click)
        self.root.bind("<ButtonRelease-1>", self._finish_global_drag)
        self.root.bind("<B1-Motion>", self._handle_global_drag)

        right_panel = ttk.Frame(self.root)
        right_panel.grid(row=1, column=2, sticky="nsew", padx=(6, 12), pady=(0, 12))
        right_panel.rowconfigure(1, weight=1)
        right_panel.columnconfigure(0, weight=1)

        inspector = ttk.LabelFrame(right_panel, text="Propiedades del bloque", padding=10)
        inspector.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        inspector.columnconfigure(1, weight=1)

        ttk.Label(inspector, text="Tipo").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Label(inspector, textvariable=self.selected_type_var).grid(
            row=0, column=1, sticky="w"
        )

        ttk.Label(inspector, text="Contenido").grid(
            row=1, column=0, sticky="nw", padx=(0, 8), pady=(10, 0)
        )
        self.content_entry = ttk.Entry(inspector, textvariable=self.content_var)
        self.content_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        self.content_entry.bind("<KeyRelease>", self._update_selected_content)

        ttk.Label(
            inspector,
            text="Selecciona un bloque y edita aqui su texto o condicion.",
            wraplength=320,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        output_frame = ttk.LabelFrame(right_panel, text="Codigo generado", padding=10)
        output_frame.grid(row=1, column=0, sticky="nsew")
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        notebook = ttk.Notebook(output_frame)
        notebook.grid(row=0, column=0, sticky="nsew")

        c_frame = ttk.Frame(notebook, padding=4)
        c_frame.rowconfigure(0, weight=1)
        c_frame.columnconfigure(0, weight=1)
        self.c_text = tk.Text(
            c_frame,
            wrap="none",
            font=("Consolas", 11),
            state="disabled",
            background="#f6fff7",
        )
        self.c_text.grid(row=0, column=0, sticky="nsew")
        c_scroll = ttk.Scrollbar(c_frame, orient="vertical", command=self.c_text.yview)
        c_scroll.grid(row=0, column=1, sticky="ns")
        self.c_text.configure(yscrollcommand=c_scroll.set)

        asm_frame = ttk.Frame(notebook, padding=4)
        asm_frame.rowconfigure(0, weight=1)
        asm_frame.columnconfigure(0, weight=1)
        self.asm_text = tk.Text(
            asm_frame,
            wrap="none",
            font=("Consolas", 11),
            state="disabled",
            background="#fff8f3",
        )
        self.asm_text.grid(row=0, column=0, sticky="nsew")
        asm_scroll = ttk.Scrollbar(asm_frame, orient="vertical", command=self.asm_text.yview)
        asm_scroll.grid(row=0, column=1, sticky="ns")
        self.asm_text.configure(yscrollcommand=asm_scroll.set)

        notebook.add(c_frame, text="Codigo C")
        notebook.add(asm_frame, text="Assembler MIPS")

    def _start_palette_drag(self, _event: tk.Event, block_type: str) -> None:
        self.dragging_palette_type = block_type
        self.dragging_block_id = None
        self.status_var.set(
            f"Suelta '{BLOCK_STYLES[block_type]['label']}' dentro del lienzo para agregarlo."
        )

    def _handle_global_drag(self, event: tk.Event) -> None:
        if self.dragging_block_id is not None:
            canvas_x = self.flow_canvas.canvasx(event.x_root - self.flow_canvas.winfo_rootx())
            canvas_y = self.flow_canvas.canvasy(event.y_root - self.flow_canvas.winfo_rooty())
            block = self._find_block(self.dragging_block_id)
            if block is None:
                return
            block.x = canvas_x - self.drag_offset_x
            block.y = canvas_y - self.drag_offset_y
            self._redraw_canvas()

    def _finish_global_drag(self, event: tk.Event) -> None:
        if self.dragging_palette_type is not None:
            x_root = event.x_root
            y_root = event.y_root
            left = self.flow_canvas.winfo_rootx()
            top = self.flow_canvas.winfo_rooty()
            right = left + self.flow_canvas.winfo_width()
            bottom = top + self.flow_canvas.winfo_height()

            if left <= x_root <= right and top <= y_root <= bottom:
                canvas_x = self.flow_canvas.canvasx(x_root - left)
                canvas_y = self.flow_canvas.canvasy(y_root - top)
                self._add_block(self.dragging_palette_type, canvas_x, canvas_y)
                self.status_var.set("Bloque agregado. Ahora puedes moverlo o editarlo.")
            else:
                self.status_var.set("El bloque no se solto dentro del lienzo.")

        self.dragging_palette_type = None
        self.dragging_block_id = None

    def _handle_canvas_click(self, event: tk.Event) -> None:
        current = self.flow_canvas.find_withtag("current")
        if not current:
            self._select_block(None)
            return

        tags = self.flow_canvas.gettags(current[0])
        block_tag = next((tag for tag in tags if tag.startswith("block-")), None)
        if block_tag is None:
            self._select_block(None)
            return

        block_id = int(block_tag.split("-", 1)[1])
        self._select_block(block_id)
        block = self._find_block(block_id)
        if block is None:
            return
        self.dragging_block_id = block_id
        self.dragging_palette_type = None
        self.drag_offset_x = event.x - block.x
        self.drag_offset_y = event.y - block.y

    def _add_block(self, block_type: str, x: float, y: float, content: str | None = None) -> None:
        block = FlowBlock(
            block_id=self.next_block_id,
            block_type=block_type,
            x=max(30, x - self.BLOCK_WIDTH / 2),
            y=max(20, y - self.BLOCK_HEIGHT / 2),
            content=DEFAULT_CONTENT[block_type] if content is None else content,
        )
        self.next_block_id += 1
        self.blocks.append(block)
        self._select_block(block.block_id)
        self._redraw_canvas()

    def _find_block(self, block_id: int) -> FlowBlock | None:
        for block in self.blocks:
            if block.block_id == block_id:
                return block
        return None

    def _select_block(self, block_id: int | None) -> None:
        self.selected_block_id = block_id
        block = self._find_block(block_id) if block_id is not None else None
        if block is None:
            self.selected_type_var.set("Sin seleccion")
            self.content_var.set("")
        else:
            self.selected_type_var.set(BLOCK_STYLES[block.block_type]["label"])
            self.content_var.set(block.content)
        self._redraw_canvas()

    def _update_selected_content(self, _event: tk.Event) -> None:
        block = self._find_block(self.selected_block_id) if self.selected_block_id is not None else None
        if block is None:
            return
        block.content = self.content_var.get()
        self._redraw_canvas()

    def _delete_selected_block(self) -> None:
        if self.selected_block_id is None:
            return
        self.blocks = [block for block in self.blocks if block.block_id != self.selected_block_id]
        self._select_block(None)
        self._redraw_canvas()
        self.status_var.set("Bloque eliminado.")

    def _clear_all(self) -> None:
        self.blocks.clear()
        self._select_block(None)
        self._set_output(self.c_text, "")
        self._set_output(self.asm_text, "")
        self._redraw_canvas()
        self.status_var.set("Lienzo limpio.")

    def _load_example(self) -> None:
        self.blocks.clear()
        self.next_block_id = 1
        self._add_block("inicio", 230, 70, "")
        self._add_block("proceso", 230, 170, "a = 10")
        self._add_block("proceso", 230, 270, "b = 20")
        self._add_block("decision", 230, 370, "a < b")
        self._add_block("salida", 330, 470, "b")
        self._add_block("finsi", 230, 570, "")
        self._add_block("fin", 230, 670, "")
        self.generate_from_diagram()

    def _set_output(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _sorted_blocks(self) -> list[FlowBlock]:
        return sorted(self.blocks, key=lambda block: (block.y, block.x))

    def _diagram_to_source(self) -> str:
        if not self.blocks:
            raise CompilerError("Debes colocar al menos un bloque en el lienzo.")

        blocks = self._sorted_blocks()
        lines: list[str] = []
        indent_level = 0
        start_count = 0
        end_count = 0

        for block in blocks:
            if block.block_type == "inicio":
                start_count += 1
                lines.append("inicio")
                continue

            if block.block_type == "fin":
                end_count += 1
                if indent_level != 0:
                    raise CompilerError("Hay un bloque 'si' sin su bloque 'FinSi'.")
                lines.append("fin")
                continue

            if start_count == 0:
                raise CompilerError("El diagrama debe comenzar con un bloque 'Inicio'.")

            if block.block_type == "finsi":
                if indent_level == 0:
                    raise CompilerError("Se encontro un bloque 'FinSi' sin una decision previa.")
                indent_level -= 1
                lines.append("    " * indent_level + "finsi")
                continue

            prefix = "    " * indent_level

            if block.block_type == "proceso":
                if "=" not in block.content:
                    raise CompilerError(
                        "Los bloques de proceso deben tener una asignacion, por ejemplo 'a = 10'."
                    )
                lines.append(prefix + block.content.strip())
                continue

            if block.block_type == "salida":
                content = block.content.strip()
                if not content:
                    raise CompilerError("Los bloques de salida deben tener una expresion.")
                lines.append(prefix + f"escribir({content})")
                continue

            if block.block_type == "decision":
                content = block.content.strip()
                if not content:
                    raise CompilerError("Los bloques de decision deben tener una condicion.")
                lines.append(prefix + f"si ({content}) entonces")
                indent_level += 1
                continue

        if start_count == 0:
            raise CompilerError("Falta el bloque 'Inicio'.")
        if end_count == 0:
            raise CompilerError("Falta el bloque 'Fin'.")
        if end_count > 1:
            raise CompilerError("Solo debe existir un bloque 'Fin'.")

        return "\n".join(lines)

    def generate_from_diagram(self) -> None:
        try:
            source = self._diagram_to_source()
            program = parse_source(source)
            c_code = generate_c_code(program)
            assembler = generate_assembler(program)
        except CompilerError as error:
            self._set_output(self.c_text, "")
            self._set_output(self.asm_text, "")
            self.status_var.set("El diagrama tiene errores.")
            messagebox.showerror("Error de diagrama", str(error))
            return

        self._set_output(self.c_text, c_code)
        self._set_output(self.asm_text, assembler)
        self.status_var.set("Codigo C y assembler generados desde el diagrama.")

    def _redraw_canvas(self) -> None:
        self.flow_canvas.delete("all")

        ordered = self._sorted_blocks()
        centers: list[tuple[float, float]] = []

        for block in ordered:
            self._draw_block(block)
            centers.append((block.x + self.BLOCK_WIDTH / 2, block.y + self.BLOCK_HEIGHT))

        for index in range(len(centers) - 1):
            x1, y1 = centers[index]
            x2, y2 = centers[index + 1]
            self.flow_canvas.create_line(
                x1,
                y1,
                x2,
                y2 - self.BLOCK_HEIGHT + 8,
                arrow=tk.LAST,
                fill="#546275",
                width=2,
            )

        bbox = self.flow_canvas.bbox("all")
        if bbox is None:
            bbox = (0, 0, 700, 700)
        self.flow_canvas.configure(scrollregion=(0, 0, max(900, bbox[2] + 80), max(900, bbox[3] + 80)))

    def _draw_block(self, block: FlowBlock) -> None:
        style = BLOCK_STYLES[block.block_type]
        x1 = block.x
        y1 = block.y
        x2 = block.x + self.BLOCK_WIDTH
        y2 = block.y + self.BLOCK_HEIGHT
        outline = "#d12f2f" if block.block_id == self.selected_block_id else style["outline"]
        width = 3 if block.block_id == self.selected_block_id else 2
        tag = f"block-{block.block_id}"

        if style["shape"] == "oval":
            self.flow_canvas.create_oval(
                x1, y1, x2, y2, fill=style["fill"], outline=outline, width=width, tags=(tag, "block")
            )
        elif style["shape"] == "diamond":
            self.flow_canvas.create_polygon(
                (x1 + x2) / 2,
                y1,
                x2,
                (y1 + y2) / 2,
                (x1 + x2) / 2,
                y2,
                x1,
                (y1 + y2) / 2,
                fill=style["fill"],
                outline=outline,
                width=width,
                tags=(tag, "block"),
            )
        elif style["shape"] == "para":
            skew = 24
            self.flow_canvas.create_polygon(
                x1 + skew,
                y1,
                x2,
                y1,
                x2 - skew,
                y2,
                x1,
                y2,
                fill=style["fill"],
                outline=outline,
                width=width,
                tags=(tag, "block"),
            )
        else:
            self.flow_canvas.create_rectangle(
                x1, y1, x2, y2, fill=style["fill"], outline=outline, width=width, tags=(tag, "block")
            )

        label = style["label"]
        text = label if not block.content.strip() else f"{label}\n{block.content.strip()}"
        self.flow_canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=text,
            width=self.BLOCK_WIDTH - 30,
            font=("Segoe UI", 10, "bold"),
            tags=(tag, "block"),
        )


def launch_app() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    CompilerGUI(root)
    root.mainloop()
