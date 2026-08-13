import { useEffect, useMemo, useRef, useState } from "react";
import "./SearchableSelect.css";

interface SearchableSelectProps {
  label: string;
  value: string;
  options: string[];
  placeholder?: string;
  onChange: (value: string) => void;
}

export function SearchableSelect({ label, value, options, placeholder = "Todas", onChange }: SearchableSelectProps) {
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

  function selectValue(v: string) {
    onChange(v);
    setQuery("");
    setOpen(false);
  }

  return (
    <div className="searchable-select" ref={containerRef}>
      <span className="searchable-select__label">{label}</span>
      <div className="searchable-select__control">
        <input
          type="text"
          value={open ? query : value}
          placeholder={placeholder}
          onFocus={() => setQuery("")}
          onClick={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
        />
        {value && (
          <button
            type="button"
            className="searchable-select__clear"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => selectValue("")}
            aria-label={`Limpiar ${label}`}
          >
            ×
          </button>
        )}
      </div>
      {open && (
        <ul className="searchable-select__menu">
          <li
            className={`searchable-select__option${value === "" ? " searchable-select__option--active" : ""}`}
            onMouseDown={() => selectValue("")}
          >
            {placeholder}
          </li>
          {filtered.map((o) => (
            <li
              key={o}
              className={`searchable-select__option${o === value ? " searchable-select__option--active" : ""}`}
              onMouseDown={() => selectValue(o)}
            >
              {o}
            </li>
          ))}
          {filtered.length === 0 && <li className="searchable-select__empty">Sin resultados</li>}
        </ul>
      )}
    </div>
  );
}
