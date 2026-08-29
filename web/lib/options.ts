// Mirrors app/services/tutor_rag_service.py's _ordered_option_keys: options
// are keyed however the source paper labels them ("1"-"5", or "A"-"D" on
// older data); correct_answer/selected_answer is a 0-based index into this
// ordering. Sorted numerically when keys are digits so "2" < "10".
export function orderedOptionKeys(options: Record<string, string>): string[] {
  return Object.keys(options).sort((a, b) => {
    const [na, nb] = [Number(a), Number(b)];
    const bothDigits = /^\d+$/.test(a) && /^\d+$/.test(b);
    return bothDigits ? na - nb : a.localeCompare(b);
  });
}
