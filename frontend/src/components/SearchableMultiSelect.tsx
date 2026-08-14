import { useEffect, useMemo, useRef, useState } from "react";
import "./SearchableSelect.css";

interface SearchableMultiSelectProps {
  label: string;
  values: string[];
  options: string[];
  placeholder?: string;
  onChange: (values: string[]) => void;
}

// Variante de SearchableSelect que permite elegir mas de un valor. Mismos
// estilos (reusa SearchableSelect.css) pero el menu no se cierra al elegir
// una opcion — cada click prende/apaga esa opcion, como un grupo de checkbox.
export function SearchableMultiSelect({ label, values, options, placeholder = "Todos", onChange }: SearchableMultiSelectProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.toLowerCase().includes(q));
  }, [options, query]);

  function toggleValue(v: string) {
    onChange(values.includes(v) ? values.filter((x) => x !== v) : [...values, v]);
  }

  const textoControl = values.join(", ");

  return (
    <div className="searchable-select" ref={containerRef}>
      <span className="searchable-select__label">{label}</span>
      <div className="searchable-select__control">
        <input
          type="text"
          value={open ? query : textoControl}
          placeholder={placeholder}
          onFocus={() => setQuery("")}
          onClick={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
        />
        {values.length > 0 && (
          <button
            type="button"
            className="searchable-select__clear"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => onChange([])}
            aria-label={`Limpiar ${label}`}
          >
            ×
          </button>
        )}
      </div>
      {open && (
        <ul className="searchable-select__menu">
          {filtered.map((o) => {
            const activo = values.includes(o);
            return (
              <li
                key={o}
                className={`searchable-select__option searchable-select__option--multi${activo ? " searchable-select__option--active" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  toggleValue(o);
                }}
              >
                <span className="searchable-select__checkbox">{activo ? "✓" : ""}</span>
                {o}
              </li>
            );
          })}
          {filtered.length === 0 && <li className="searchable-select__empty">Sin resultados</li>}
        </ul>
      )}
    </div>
  );
}
