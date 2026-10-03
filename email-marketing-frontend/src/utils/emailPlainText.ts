export function hasHtmlMarkup(html: string): boolean {
    return /<[a-z][\s>]/i.test((html || '').trim());
}

export function isRichMarketingHtml(html: string): boolean {
    const content = html.trim();
    if (!content) {
        return false;
    }
    const lower = content.toLowerCase();
    if (/<(table|td|tr|tbody|thead)[\s>]/i.test(lower)) {
        return true;
    }
    if (/<style[\s>]/i.test(content)) {
        return true;
    }
    if (lower.includes('<html') && content.length > 300) {
        return true;
    }
    if (/<div[\s>]/i.test(content) && content.length > 800) {
        return true;
    }
    return content.length > 1500;
}

export function normalizeEmailHtml(html: string): string {
    const content = (html || '').trim();
    if (!content) {
        return content;
    }
    const lower = content.toLowerCase();
    if (lower.includes('<html') && lower.includes('<body')) {
        return content;
    }
    return (
        '<!DOCTYPE html>' +
        '<html><head><meta charset="utf-8"></head>' +
        `<body style="margin:0;padding:0;font-family:Arial,sans-serif;line-height:1.5;color:#111827;">${content}</body>` +
        '</html>'
    );
}

function normalizePlainTextUrls(text: string): string {
    let normalized = text.replace(/([^\s(]+)\s*\((https?:\/\/[^)]+)\)/gi, '$2');
    const paragraphs: string[] = [];
    for (const block of normalized.split(/\n\n+/)) {
        const lines: string[] = [];
        for (const rawLine of block.split('\n')) {
            const line = rawLine.trim();
            if (!line) {
                continue;
            }
            lines.push(line);
            if (/^www\.[^\s]+$/i.test(line)) {
                const httpsUrl = `https://${line}`;
                if (!lines.some((existing) => existing.toLowerCase().startsWith('http') && existing.toLowerCase().includes(httpsUrl.toLowerCase()))) {
                    lines.push(httpsUrl);
                }
            }
        }
        if (lines.length) {
            paragraphs.push(lines.join('\n'));
        }
    }
    return paragraphs.join('\n\n');
}

function inboxBlockStyle(compact = false): string {
    const base = 'font-family:Georgia,serif;font-size:15px;color:#222;text-align:left;';
    return compact ? `margin:0 0 14px;${base}line-height:1.2;` : `margin:0 0 14px;${base}line-height:1.6;`;
}

const INBOX_ALLOWED_TAGS = new Set(['p', 'div', 'br', 'a', 'span', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li']);
const INBOX_ALLOWED_ATTRS = new Set(['style', 'href', 'target', 'rel', 'align']);

function mergeAlignIntoStyle(tagHtml: string, attrs: Record<string, string>): Record<string, string> {
    const alignMatch = /align=["']([^"']+)["']/i.exec(tagHtml);
    if (!alignMatch) {
        return attrs;
    }
    const alignValue = alignMatch[1].trim().toLowerCase();
    if (!['left', 'right', 'center', 'justify'].includes(alignValue)) {
        return attrs;
    }
    const style = attrs.style || '';
    if (style.toLowerCase().includes('text-align')) {
        return attrs;
    }
    const separator = style && !style.trim().endsWith(';') ? ';' : '';
    return { ...attrs, style: `${style}${separator}text-align:${alignValue};`.replace(/^;/, '') };
}

export function sanitizeSimpleInboxHtml(html: string): string {
    let content = (html || '').trim();
    if (!content) {
        return '';
    }

    content = content.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, '');
    content = content.replace(/<!DOCTYPE[^>]*>/gi, '');
    content = content.replace(/<\/?(?:html|head|body)[^>]*>/gi, '');
    content = content.replace(/<\/tr\s*>/gi, '\n');
    content = content.replace(/<\/td\s*>/gi, ' ');
    content = content.replace(/<(table|tbody|thead|tfoot|tr|td|th)[^>]*>/gi, '');

    return content.replace(/<[^>]+>/gi, (tagHtml) => {
        const lowered = tagHtml.toLowerCase();
        if (lowered.startsWith('<br')) {
            return '<br>';
        }

        const tagMatch = /^<\/?([a-z][a-z0-9]*)/i.exec(tagHtml);
        if (!tagMatch) {
            return '';
        }
        const name = tagMatch[1].toLowerCase();
        if (!INBOX_ALLOWED_TAGS.has(name)) {
            return '';
        }
        if (tagHtml.startsWith('</')) {
            return `</${name}>`;
        }

        const attrs: Record<string, string> = {};
        for (const attrName of INBOX_ALLOWED_ATTRS) {
            const attrMatch = new RegExp(`${attrName}=["']([^"']*)["']`, 'i').exec(tagHtml);
            if (attrMatch) {
                attrs[attrName.toLowerCase()] = attrMatch[1].trim();
            }
        }

        if (name === 'a') {
            const href = attrs.href || '';
            if (!href || href === '#') {
                return '';
            }
            attrs.target = attrs.target || '_blank';
            attrs.rel = attrs.rel || 'noopener noreferrer';
        }

        const mergedAttrs = mergeAlignIntoStyle(tagHtml, attrs);
        delete mergedAttrs.align;

        const attrString = Object.entries(mergedAttrs)
            .map(([key, value]) => `${key}="${value}"`)
            .join(' ');
        return attrString ? `<${name} ${attrString}>` : `<${name}>`;
    }).trim();
}

function wrapInboxPriorityHtml(bodyHtml: string, fromName?: string): string {
    const body = (bodyHtml || '').trim();
    if (!body) {
        return '';
    }

    const signatureName = (fromName || '').trim();
    let signature = '';
    if (signatureName && !body.toLowerCase().includes(signatureName.toLowerCase())) {
        signature =
            `<p style="margin:18px 0 0;${inboxBlockStyle(true).replace('margin:0 0 14px;', '')}">` +
            `Regards,<br>${signatureName}</p>`;
    }

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>' +
        `<body style="margin:0;padding:0;background:#fff;text-align:left;">${body}${signature}</body></html>`
    );
}

function linkifyPlainTextForHtml(text: string): string {
    const linked = text.replace(/https?:\/\/[^\s<>&"]+/gi, (url) => {
        return `<a href="${url}" style="color:#1a73e8;text-decoration:underline;" target="_blank" rel="noopener noreferrer">${url}</a>`;
    });
    return linked.replace(/(?<!:\/\/)(?<![\w.@])www\.[^\s<>&"]+/gi, (url) => {
        const href = `https://${url}`;
        return `<a href="${href}" style="color:#1a73e8;text-decoration:underline;" target="_blank" rel="noopener noreferrer">${url}</a>`;
    });
}

export function formatInboxFriendlyHtml(plainText: string, fromName?: string): string {
    const plain = normalizePlainTextUrls((plainText || '').trim());
    if (!plain) {
        return '';
    }

    const blocks = plain
        .split(/\n\n+/)
        .map((block) => block.trim())
        .filter(Boolean);
    const bodyHtml = blocks
        .map((block) => {
            const compact = block.includes('\n') && block.split('\n').length <= 5;
            return (
                `<p style="${inboxBlockStyle(compact)}">` +
                `${linkifyPlainTextForHtml(block.replace(/\n/g, '<br>'))}</p>`
            );
        })
        .join('');

    const signatureName = (fromName || '').trim();
    let signature = '';
    if (signatureName && !plain.toLowerCase().includes(signatureName.toLowerCase())) {
        signature =
            `<p style="margin:18px 0 0;${inboxBlockStyle(true).replace('margin:0 0 14px;', '')}">` +
            `Regards,<br>${signatureName}</p>`;
    }

    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>' +
        `<body style="margin:0;padding:0;background:#fff;text-align:left;">${bodyHtml}${signature}</body></html>`
    );
}

export function htmlToPlainText(html: string): string {
    if (!html.trim()) {
        return '';
    }

    let text = html.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, '');
    text = text.replace(
        /<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi,
        (_match, url: string, label: string) => {
            const cleanUrl = (url || '').trim();
            if (!cleanUrl || cleanUrl === '#') {
                return label.replace(/<[^>]+>/g, '').trim();
            }
            return cleanUrl;
        },
    );
    text = text.replace(/<\/td\s*>/gi, ' ');
    text = text.replace(/<br\s*\/?>/gi, '\n');
    text = text.replace(/<\/p\s*>/gi, '\n\n');
    text = text.replace(/<\/tr\s*>/gi, '\n');
    text = text.replace(/<\/li\s*>/gi, '\n');
    text = text.replace(/<[^>]+>/g, '');
    text = text.replace(/&nbsp;/g, ' ');
    text = text.replace(/&amp;/g, '&');
    text = text.replace(/\n{3,}/g, '\n\n');
    const paragraphs = text
        .split(/\n\n+/)
        .map((paragraph) =>
            paragraph
                .split('\n')
                .map((line) => line.replace(/\s+/g, ' ').trim())
                .filter(Boolean)
                .join('\n'),
        )
        .filter(Boolean);
    return normalizePlainTextUrls(paragraphs.join('\n\n'));
}

function plainHasContactDetails(text: string): boolean {
    if (!text.trim()) {
        return false;
    }
    const lowered = text.toLowerCase();
    if (lowered.includes('http') || lowered.includes('www.')) {
        return true;
    }
    return /\+?\d[\d\s\-()]{7,}/.test(text);
}

export function resolveInboxPriorityPlain(html: string, plainText: string): string {
    const plainFromHtml = htmlToPlainText(html);
    const plainFromField = plainText.trim();

    if (plainFromField && plainFromHtml) {
        if (
            plainFromHtml.length > plainFromField.length + 20 ||
            plainFromHtml.includes(plainFromField) ||
            (!plainHasContactDetails(plainFromField) && plainHasContactDetails(plainFromHtml))
        ) {
            return normalizePlainTextUrls(plainFromHtml);
        }
        return normalizePlainTextUrls(plainFromField);
    }
    if (plainFromHtml) {
        return normalizePlainTextUrls(plainFromHtml);
    }
    return normalizePlainTextUrls(plainFromField);
}

export function buildCampaignPreviewHtml(
    htmlContent: string,
    plainText: string,
    inboxPriority: boolean,
    fromName?: string,
): { html: string; mode: 'designed' | 'inbox-plain' | 'standard' } {
    const hasMarkup = hasHtmlMarkup(htmlContent);

    if (inboxPriority) {
        const plain = resolveInboxPriorityPlain(htmlContent, plainText);
        const sanitized = htmlContent.trim() ? sanitizeSimpleInboxHtml(htmlContent) : '';
        if (sanitized) {
            return { html: wrapInboxPriorityHtml(sanitized, fromName), mode: 'inbox-plain' };
        }
        return { html: formatInboxFriendlyHtml(plain, fromName), mode: 'inbox-plain' };
    }

    if (hasMarkup && htmlContent.trim()) {
        return { html: normalizeEmailHtml(htmlContent), mode: 'designed' };
    }

    const fallbackPlain = plainText.trim() || htmlToPlainText(htmlContent);
    return { html: formatInboxFriendlyHtml(fallbackPlain, fromName), mode: 'standard' };
}
