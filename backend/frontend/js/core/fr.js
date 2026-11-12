// The French words, looked up by their English text (see i18n.js).
// backend/tests/test_frontend.py fails when a string has no French here.

export const FR = {
  // index.html
  Settings: "Réglages",
  "Night mode": "Mode nuit",
  Language: "Langue",
  Courses: "Cours",
  "Each course's colour is used for its events.": "La couleur de chaque cours sert pour ses événements.",
  "Code, e.g. ABC123": "Code, p. ex. ABC123",
  "New course's code": "Code du nouveau cours",
  "Add course": "Ajouter le cours",
  Views: "Vues",
  Upcoming: "À venir",
  Week: "Semaine",
  Month: "Mois",
  "Next 14 days": "14 prochains jours",
  "+ Add an event": "+ Ajouter un événement",
  "← Earlier": "← Avant",
  Today: "Aujourd'hui",
  "Later →": "Après →",
  "← Back": "← Retour",
  "New event": "Nouvel événement",
  "Edit event": "Modifier l'événement",
  Title: "Titre",
  Type: "Type",
  "Course code (empty for none)": "Code du cours (vide pour aucun)",
  Date: "Date",
  "Start time": "Heure de début",
  "End time": "Heure de fin",
  "Due time": "Heure de remise",
  "Leave the times empty for an all-day event.": "Laissez les heures vides pour un événement d'une journée entière.",
  "A deadline has a due time, like 23:59. Leave it empty if it's due some time that day.":
    "Une remise a une heure limite, comme 23:59. Laissez-la vide si c'est dû pendant la journée.",
  Done: "Fait",
  Location: "Lieu",
  Details: "Détails",
  'Source (Moodle link or "Email: subject, date")': "Source (lien Moodle ou « Email: sujet, date »)",
  "This event is part of a weekly series. Changes here apply to this one only.":
    "Cet événement fait partie d'une série hebdomadaire. Les changements ici ne s'appliquent qu'à lui.",
  Save: "Enregistrer",
  Delete: "Supprimer",
  "Delete the whole series": "Supprimer toute la série",

  // Event types
  Class: "Cours",
  Lab: "Labo",
  Exam: "Examen",
  Deadline: "Remise",
  Meeting: "Réunion",
  Work: "Travail",
  Personal: "Personnel",
  Other: "Autre",

  // Scripts
  "Loading...": "Chargement...",
  Tomorrow: "Demain",
  Overdue: "En retard",
  "Nothing in the next 14 days.": "Rien dans les 14 prochains jours.",
  "Done: {title}": "Fait : {title}",
  done: "fait",
  "All day": "Toute la journée",
  "Due {time}": "Remise {time}",
  "Week of {date}": "Semaine du {date}",
  "Add an event on {date} ({iso})": "Ajouter un événement le {date} ({iso})",
  "Click again to delete": "Cliquez encore pour supprimer",
  "Click again to delete every event of the series": "Cliquez encore pour supprimer tous les événements de la série",
  "Give the event a title.": "Donnez un titre à l'événement.",
  "Choose a date.": "Choisissez une date.",
  "Saved: {title}, {date}": "Enregistré : {title}, {date}",
  "{n} event": "{n} événement",
  "{n} events": "{n} événements",
  Remove: "Retirer",
  "Click again to remove": "Cliquez encore pour retirer",
  "Click again: removes its {count} too": "Cliquez encore : retire aussi ses {count}",
  "Remove the course {code}": "Retirer le cours {code}",
  "No courses yet. Add one here, or add an event with a course code.":
    "Aucun cours pour l'instant. Ajoutez-en un ici, ou ajoutez un événement avec un code de cours.",
  "{code}: colour": "{code} : couleur",
  Colour: "Couleur",
  "{code}: code": "{code} : code",
  "{code}: name": "{code} : nom",
  "Course name (optional)": "Nom du cours (facultatif)",
  "Error {status}": "Erreur {status}",
  "The server didn't answer (error {status}). Try again in a minute.":
    "Le serveur n'a pas répondu (erreur {status}). Réessayez dans une minute.",
  "Can't reach the app. Check that it's running.":
    "Impossible de joindre l'application. Vérifiez qu'elle est en marche.",

  // Messages from the server
  "Course not found.": "Cours introuvable.",
  "Event not found.": "Événement introuvable.",
  "Another course already has this code.": "Un autre cours a déjà ce code.",
  "This course still has events.": "Ce cours a encore des événements.",
  "A course code is letters and digits, like ABC123.":
    "Un code de cours est fait de lettres et de chiffres, comme ABC123.",
  "An end time needs a start time.": "Une heure de fin demande une heure de début.",
  "A deadline has only a due time, no end time.": "Une remise n'a qu'une heure limite, pas d'heure de fin.",
  "Write a local time like 13:30.": "Écrivez une heure locale comme 13:30.",
  "The end time must be after the start time.": "L'heure de fin doit être après l'heure de début.",
  "The title, type and date can't be empty.": "Le titre, le type et la date ne peuvent pas être vides.",

  // Calendars and this week's list (index.html, scripts, then server messages)
  Calendars: "Calendriers",
  Calendar: "Calendrier",
  "The tabs under the top bar. Every event is on one of them.":
    "Les onglets sous la barre du haut. Chaque événement est dans l'un d'eux.",
  All: "Tous",
  "+ New calendar": "+ Nouveau calendrier",
  "New calendar": "Nouveau calendrier",
  Rename: "Renommer",
  "Rename the calendar {name}": "Renommer le calendrier {name}",
  "Name of the calendar {name}": "Nom du calendrier {name}",
  "Remove the calendar {name}": "Retirer le calendrier {name}",
  "{n} to-do": "{n} tâche",
  "{n} to-dos": "{n} tâches",
  "{a} and {b}": "{a} et {b}",
  "{n} not done on the weekly lists": "{n} pas faites dans les listes de la semaine",
  "This week's list": "Liste de la semaine",
  "{done} of {total} done": "{done} sur {total} faites",
  "Nothing on the list yet.": "Rien sur la liste pour l'instant.",
  "Done: {text}": "Fait : {text}",
  "To-do: {text}": "Tâche : {text}",
  "Delete: {text}": "Supprimer : {text}",
  "Something to do this week": "Quelque chose à faire cette semaine",
  "Add to this week's list": "Ajouter à la liste de la semaine",
  Add: "Ajouter",
  "Move unfinished to next week": "Reporter ce qui reste à la semaine prochaine",
  "Moved {n} to next week.": "{n} reportée(s) à la semaine prochaine.",
  "Bring next week's {n} unfinished here": "Ramener ici les {n} tâches non faites de la semaine prochaine",
  "Brought {n} from next week.": "{n} ramenée(s) de la semaine prochaine.",
  "To do": "À faire",
  "To do, week of {date}": "À faire, semaine du {date}",
  "Nothing yet.": "Rien pour l'instant.",
  "↑ Next week's ({n})": "↑ Semaine suivante ({n})",
  "Bring next week's {n} unfinished to the week of {date}":
    "Ramener les {n} tâches non faites de la semaine suivante à la semaine du {date}",
  "Calendar not found.": "Calendrier introuvable.",
  "This calendar doesn't exist.": "Ce calendrier n'existe pas.",
  "Another calendar already has this name.": "Un autre calendrier a déjà ce nom.",
  "The last calendar can't be removed.": "Le dernier calendrier ne peut pas être retiré.",
  "This calendar still has events or to-dos.": "Ce calendrier a encore des événements ou des tâches.",
  "Give the calendar a name.": "Donnez un nom au calendrier.",
  "A week is given by its Monday.": "Une semaine se donne par son lundi.",
  "An item is listed twice.": "Un élément est en double.",
  "These items aren't all on that week's list.": "Ces éléments ne sont pas tous sur la liste de cette semaine.",
  "Drag to move: {text}. Or use the up and down arrow keys.":
    "Glisser pour déplacer : {text}. Ou utilisez les flèches haut et bas.",
  "Give a week, or from and to.": "Donnez une semaine, ou un début et une fin.",
  "Write what there is to do.": "Écrivez ce qu'il y a à faire.",
  "To-do not found.": "Tâche introuvable.",
  // Import: the tab, the preview, past imports in Settings, and the server's messages
  // (the parser's line messages are matched by their template, with {values} kept).
  Import: "Importer",
  "Put new events in": "Mettre les nouveaux événements dans",
  "Import events": "Importer des événements",
  "Lines to import (one event per line)": "Lignes à importer (un événement par ligne)",
  "Where the lines come from": "D'où viennent les lignes",
  "Guess from the source column": "Deviner d'après la colonne source",
  Moodle: "Moodle",
  Email: "Courriel",
  "Typed by hand": "Tapé à la main",
  Preview: "Aperçu",
  "What the import will do": "Ce que l'importation va faire",
  Line: "Ligne",
  Status: "État",
  Time: "Heure",
  Course: "Cours",
  "Details and place": "Détails et lieu",
  "Add to calendar": "Ajouter au calendrier",
  "Undo this import": "Annuler cette importation",
  "Past imports": "Importations passées",
  "Undo removes the events an import added and puts back the ones it changed.":
    "Annuler retire les événements qu'une importation a ajoutés et remet ceux qu'elle a changés.",
  "How to write the lines": "Comment écrire les lignes",
  "One event per line, with the fields in this order, separated by |:":
    "Un événement par ligne, avec les champs dans cet ordre, séparés par | :",
  "The day: 2026-11-24 or Tue Nov 24 (French works too: mardi 24 novembre). If you write the weekday, it must match the date, or the line is refused. Without a year, the nearest one is used.":
    "Le jour : 2026-11-24 ou Tue Nov 24 (le français marche aussi : mardi 24 novembre). Si vous écrivez le jour de la semaine, il doit correspondre à la date, sinon la ligne est refusée. Sans année, la plus proche est prise.",
  "13:30-15:20, or a start and a length: 13:30 75 min. For a deadline, only the due time: 23:59. Write all day when there is no time.":
    "13:30-15:20, ou un début et une durée : 13:30 75 min. Pour une remise, seulement l'heure limite : 23:59. Écrivez all day (ou toute la journée) quand il n'y a pas d'heure.",
  "One of class, lab, exam, deadline, meeting, work, personal, other. French words work too: cours, labo, examen, remise, réunion.":
    "Un de class, lab, exam, deadline, meeting, work, personal, other. Les mots français marchent aussi : cours, labo, examen, remise, réunion.",
  "The course code, like ABC123, or - for no course. A code the calendar doesn't know yet adds the course.":
    "Le code du cours, comme ABC123, ou - pour aucun cours. Un code que le calendrier ne connaît pas encore ajoute le cours.",
  "Short, like Lab report 3 or Final exam.": "Court, comme Rapport de labo 3 ou Examen final.",
  "Optional free text. room: D7-2018 gives the place. weekly until 2026-12-12 repeats the event every week up to that date, and except 2026-10-13 skips one of those weeks (write except again for each week to skip).":
    "Texte libre, facultatif. room: D7-2018 donne le lieu. weekly until 2026-12-12 répète l'événement chaque semaine jusqu'à cette date, et except 2026-10-13 saute une de ces semaines (écrivez except de nouveau pour chaque semaine à sauter).",
  "Optional: the Moodle page's address, or Email: subject, date for an email.":
    "Facultatif : l'adresse de la page Moodle, ou Email: sujet, date pour un courriel.",
  "Example:": "Exemple :",
  "Press Preview to check the lines: nothing is saved until you press Add to calendar. A line with a mistake says how to fix it, and the other lines still go in. Lines already on the calendar are skipped, and an event that moved shows its old and new date.":
    "Appuyez sur Aperçu pour vérifier les lignes : rien n'est enregistré avant Ajouter au calendrier. Une ligne avec une erreur dit comment la corriger, et les autres lignes passent quand même. Les lignes déjà au calendrier sont sautées, et un événement déplacé montre son ancienne et sa nouvelle date.",
  "Draft saved.": "Brouillon enregistré.",
  "The lines changed since the preview. Press Preview again.":
    "Les lignes ont changé depuis l'aperçu. Appuyez de nouveau sur Aperçu.",
  New: "Nouveau",
  "Already there": "Déjà là",
  "Already there (earlier line)": "Déjà là (ligne plus haut)",
  Changed: "Changé",
  Error: "Erreur",
  "new course": "nouveau cours",
  weekly: "chaque semaine",
  "{new} new, {changed} changed, {already} already there, {error} with an error.":
    "{new} nouveaux, {changed} changés, {already} déjà là, {error} avec une erreur.",
  "No event lines yet.": "Aucune ligne d'événement pour l'instant.",
  "Nothing new or changed to add.": "Rien de nouveau ni de changé à ajouter.",
  "Added {added}, changed {changed}, skipped {skipped}.": "Ajoutés : {added}, changés : {changed}, sautés : {skipped}.",
  "Lines with an error, not added: {errors}.": "Lignes avec une erreur, non ajoutées : {errors}.",
  "Import undone: removed {removed}, put back {restored}.":
    "Importation annulée : {removed} retirés, {restored} remis comme avant.",
  Undo: "Annuler",
  "Undone on {date}": "Annulée le {date}",
  "Undo the import of {date}: removes the {added} events it added and puts back the {changed} it changed":
    "Annuler l'importation du {date} : retire les {added} événements ajoutés et remet les {changed} changés",
  "No imports yet.": "Aucune importation pour l'instant.",
  Monday: "lundi",
  Tuesday: "mardi",
  Wednesday: "mercredi",
  Thursday: "jeudi",
  Friday: "vendredi",
  Saturday: "samedi",
  Sunday: "dimanche",
  "Import not found.": "Importation introuvable.",
  "The calendar changed since the preview. Press Preview again.":
    "Le calendrier a changé depuis l'aperçu. Appuyez de nouveau sur Aperçu.",
  "This import was already undone.": "Cette importation a déjà été annulée.",
  "'{value}' isn't a date I can read. Write it like Tue Nov 24 or 2026-11-24.":
    "« {value} » n'est pas une date que je sais lire. Écrivez-la comme Tue Nov 24 ou 2026-11-24.",
  "'{value}' isn't a real date. Check the day and the month.":
    "« {value} » n'est pas une vraie date. Vérifiez le jour et le mois.",
  "The date is empty. Write it like Tue Nov 24 or 2026-11-24.":
    "La date est vide. Écrivez-la comme Tue Nov 24 ou 2026-11-24.",
  "'{value}' has no day of the month. Write it like Tue Nov 24 or 2026-11-24.":
    "« {value} » n'a pas de jour du mois. Écrivez-la comme Tue Nov 24 ou 2026-11-24.",
  "'{value}' has no month. Write it like Tue Nov 24 or 2026-11-24.":
    "« {value} » n'a pas de mois. Écrivez-la comme Tue Nov 24 ou 2026-11-24.",
  "{date} is a {weekday}, not a {written}. Check the date or the weekday.":
    "Le {date} est un {weekday}, pas un {written}. Vérifiez la date ou le jour de la semaine.",
  "{date} is more than a year from today. Check the year.":
    "Le {date} est à plus d'un an d'aujourd'hui. Vérifiez l'année.",
  "'{value}' isn't a time I can read. Write it like 13:30-15:20, 13:30 75 min, 23:59 or all day.":
    "« {value} » n'est pas une heure que je sais lire. Écrivez-la comme 13:30-15:20, 13:30 75 min, 23:59 ou all day.",
  "The length has to be more than 0 minutes. Write it like 13:30 75 min.":
    "La durée doit être de plus de 0 minute. Écrivez-la comme 13:30 75 min.",
  "'{value}' goes past midnight. End it at 23:59 or split it in two lines.":
    "« {value} » dépasse minuit. Finissez à 23:59 ou faites-en deux lignes.",
  "A deadline has only a due time. Write just that, like 23:59.":
    "Une remise n'a qu'une heure limite. Écrivez seulement celle-là, comme 23:59.",
  "The end ({end}) isn't after the start ({start}). Write it like 13:30-15:20.":
    "La fin ({end}) n'est pas après le début ({start}). Écrivez comme 13:30-15:20.",
  "'{value}' isn't a type. Use one of: class, lab, exam, deadline, meeting, work, personal, other.":
    "« {value} » n'est pas un type. Utilisez un de : class, lab, exam, deadline, meeting, work, personal, other.",
  "'{value}' isn't a course code. Write a code like ABC123, or - for no course.":
    "« {value} » n'est pas un code de cours. Écrivez un code comme ABC123, ou - pour aucun cours.",
  "The source is longer than 500 characters. Use the page's address, or Email: subject, date.":
    "La source dépasse 500 caractères. Utilisez l'adresse de la page, ou Email: sujet, date.",
  "Write the end of the series like weekly until 2026-12-12 (year-month-day).":
    "Écrivez la fin de la série comme weekly until 2026-12-12 (année-mois-jour).",
  "The details are longer than 5000 characters. Keep only what matters.":
    "Les détails dépassent 5000 caractères. Gardez seulement l'essentiel.",
  "except {date} only works with weekly until on the same line.":
    "except {date} ne marche qu'avec weekly until sur la même ligne.",
  "weekly until {until} is before the first date ({date}). Check both dates.":
    "weekly until {until} est avant la première date ({date}). Vérifiez les deux dates.",
  "except {date} isn't one of this series' days (every {weekday} from {first} to {until}). Check the date.":
    "except {date} n'est pas un des jours de cette série (chaque {weekday} du {first} au {until}). Vérifiez la date.",
  "There's no | between the fields. Write: date | time | type | course | title | details | source.":
    "Il n'y a pas de | entre les champs. Écrivez : date | time | type | course | title | details | source.",
  "Only {count} fields. Write: date | time | type | course | title, then details and source if you have them.":
    "Seulement {count} champs. Écrivez : date | time | type | course | title, puis details et source si vous les avez.",
  "The title is empty. Write a short title, like Lab 3.": "Le titre est vide. Écrivez un titre court, comme Lab 3.",
  "The title is longer than 200 characters. Make it shorter and put the rest in the details.":
    "Le titre dépasse 200 caractères. Raccourcissez-le et mettez le reste dans les détails.",
};
