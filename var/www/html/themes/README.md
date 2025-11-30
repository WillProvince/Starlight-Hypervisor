# 🎨 Starlight Theme System

---

## 📋 Overview

Starlight supports custom themes through a flexible JSON-based theming system. Themes modify CSS custom properties (variables) to change the appearance of the entire application.

---

## 🏠 Built-in Themes

1. **Light** (default.json) - Clean, bright interface optimized for daytime use
2. **Dark** (dark.json) - Easy on the eyes for low-light environments

---

## ✨ Creating Custom Themes

### Theme JSON Structure

Create a JSON file with the following structure:

```json
{
  "name": "My Custom Theme",
  "id": "my-custom-theme",
  "variables": {
    "bg-primary": "#f7f9fb",
    "bg-secondary": "#ffffff",
    "bg-tertiary": "#f9fafb",
    "bg-card": "#ffffff",
    "bg-sidebar": "linear-gradient(180deg, #1e293b 0%, #0f172a 100%)",
    "text-primary": "#1f2937",
    "text-secondary": "#4b5563",
    "text-tertiary": "#6b7280",
    "text-sidebar": "#ffffff",
    "border-color": "#e5e7eb",
    "shadow-sm": "0 2px 4px rgba(0, 0, 0, 0.1)",
    "shadow-md": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)"
  }
}
```

### CSS Variable Reference

| Variable | Description | Example Values |
|----------|-------------|----------------|
| `bg-primary` | Main background color | `#f7f9fb`, `#0f172a` |
| `bg-secondary` | Secondary backgrounds (topbar, etc.) | `#ffffff`, `#1e293b` |
| `bg-tertiary` | Tertiary backgrounds (subtle contrast) | `#f9fafb`, `#334155` |
| `bg-card` | Card/panel backgrounds | `#ffffff`, `#1e293b` |
| `bg-sidebar` | Sidebar background (can use gradients) | `linear-gradient(...)` |
| `text-primary` | Primary text color | `#1f2937`, `#f1f5f9` |
| `text-secondary` | Secondary text (less emphasis) | `#4b5563`, `#cbd5e1` |
| `text-tertiary` | Tertiary text (lowest emphasis) | `#6b7280`, `#94a3b8` |
| `text-sidebar` | Sidebar text color | `#ffffff`, `#f1f5f9` |
| `border-color` | Border and divider colors | `#e5e7eb`, `#334155` |
| `shadow-sm` | Small shadow effect | `0 2px 4px rgba(...)` |
| `shadow-md` | Medium shadow effect | `0 10px 15px -3px rgba(...)` |

---

## 🚀 Using Custom Themes

### Via Web UI

1. Navigate to **Settings** page
2. Scroll to **Appearance** section
3. Click **Import Custom Theme**
4. Upload your theme JSON file
5. Select your theme from the dropdown

### Exporting Themes

1. Navigate to **Settings** page
2. Scroll to **Appearance** section
3. Click **Export Current Theme**
4. Save the downloaded JSON file

---

## 💡 Theme Design Tips

1. **Contrast**: Ensure sufficient contrast between text and background colors
2. **Consistency**: Keep similar elements using similar color values
3. **Accessibility**: Test with users who have visual impairments
4. **Shadows**: Adjust shadow opacity based on your background darkness
5. **Gradients**: Sidebar background can use CSS gradients for visual interest

---

## 📖 Examples

### Ocean Theme
```json
{
  "name": "Ocean",
  "id": "ocean",
  "variables": {
    "bg-primary": "#e0f2f1",
    "bg-secondary": "#b2dfdb",
    "bg-tertiary": "#80cbc4",
    "bg-card": "#ffffff",
    "bg-sidebar": "linear-gradient(180deg, #00695c 0%, #004d40 100%)",
    "text-primary": "#004d40",
    "text-secondary": "#00695c",
    "text-tertiary": "#00796b",
    "text-sidebar": "#ffffff",
    "border-color": "#4db6ac",
    "shadow-sm": "0 2px 4px rgba(0, 77, 64, 0.1)",
    "shadow-md": "0 10px 15px -3px rgba(0, 77, 64, 0.1), 0 4px 6px -2px rgba(0, 77, 64, 0.05)"
  }
}
```

### Midnight Theme
```json
{
  "name": "Midnight",
  "id": "midnight",
  "variables": {
    "bg-primary": "#0a0e27",
    "bg-secondary": "#141937",
    "bg-tertiary": "#1e2447",
    "bg-card": "#141937",
    "bg-sidebar": "linear-gradient(180deg, #0a0e27 0%, #000000 100%)",
    "text-primary": "#e0e7ff",
    "text-secondary": "#a5b4fc",
    "text-tertiary": "#818cf8",
    "text-sidebar": "#e0e7ff",
    "border-color": "#3730a3",
    "shadow-sm": "0 2px 4px rgba(99, 102, 241, 0.3)",
    "shadow-md": "0 10px 15px -3px rgba(99, 102, 241, 0.3), 0 4px 6px -2px rgba(99, 102, 241, 0.2)"
  }
}
```

---

## 🔍 Troubleshooting

⚠️ **Theme doesn't apply**: Ensure your JSON is valid and contains all required variables.

⚠️ **Colors look wrong**: Some colors support gradients (like `bg-sidebar`), while others should be solid colors.

⚠️ **Theme not persisting**: Check browser localStorage permissions and cookies settings.

---

## 🤝 Contributing

Share your custom themes with the community! Submit a pull request with your theme JSON file in the `themes/` directory.
